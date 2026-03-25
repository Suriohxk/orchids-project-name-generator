"""
Packet capture module using Scapy.
Handles live capture and PCAP file replay for testing.
"""
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Try to import Scapy; fall back gracefully in environments without pcap access
try:
    from scapy.all import sniff, IP, TCP, UDP, ICMP, ARP, rdpcap, PacketList
    SCAPY_AVAILABLE = True
except ImportError:
    SCAPY_AVAILABLE = False
    logger.warning("Scapy not available – capture will use simulation mode.")


@dataclass
class FlowRecord:
    """Represents a single network flow aggregated from packets."""
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: str
    start_time: float
    last_time: float
    packet_count: int = 0
    byte_count: int = 0
    flags_set: set = field(default_factory=set)  # TCP flags seen
    ttl_values: List[int] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return self.last_time - self.start_time

    @property
    def pps(self) -> float:
        """Packets per second."""
        d = self.duration
        return self.packet_count / d if d > 0 else float(self.packet_count)

    @property
    def bps(self) -> float:
        """Bytes per second."""
        d = self.duration
        return self.byte_count / d if d > 0 else float(self.byte_count)

    def to_dict(self) -> dict:
        return {
            "src_ip": self.src_ip,
            "dst_ip": self.dst_ip,
            "src_port": self.src_port,
            "dst_port": self.dst_port,
            "protocol": self.protocol,
            "start_time": self.start_time,
            "last_time": self.last_time,
            "duration": self.duration,
            "packet_count": self.packet_count,
            "byte_count": self.byte_count,
            "pps": self.pps,
            "bps": self.bps,
            "flags": list(self.flags_set),
        }


class FlowAggregator:
    """
    Aggregates raw packets into flow records within a sliding time window.
    Thread-safe via a simple lock.
    """

    def __init__(self, window_seconds: float = 10.0, flow_timeout: float = 60.0):
        self.window_seconds = window_seconds
        self.flow_timeout = flow_timeout
        self._flows: Dict[Tuple, FlowRecord] = {}
        self._lock = threading.Lock()
        self._packet_buffer: deque = deque(maxlen=100_000)

    def _flow_key(self, src_ip: str, dst_ip: str, src_port: int, dst_port: int, protocol: str) -> Tuple:
        # Bidirectional key: sort src/dst so A→B and B→A share one record
        endpoints = tuple(sorted([(src_ip, src_port), (dst_ip, dst_port)]))
        return (*endpoints[0], *endpoints[1], protocol)

    def process_packet(self, pkt) -> Optional[FlowRecord]:
        """Parse a Scapy packet and update the corresponding flow record."""
        if not SCAPY_AVAILABLE or IP not in pkt:
            return None

        src_ip = pkt[IP].src
        dst_ip = pkt[IP].dst
        length = len(pkt)
        ts = float(pkt.time)

        src_port, dst_port, protocol = 0, 0, "OTHER"
        flags = set()

        if TCP in pkt:
            src_port = pkt[TCP].sport
            dst_port = pkt[TCP].dport
            protocol = "TCP"
            f = pkt[TCP].flags
            for flag_name in ["S", "A", "F", "R", "P", "U"]:
                if flag_name in str(f):
                    flags.add(flag_name)
        elif UDP in pkt:
            src_port = pkt[UDP].sport
            dst_port = pkt[UDP].dport
            protocol = "UDP"
        elif ICMP in pkt:
            protocol = "ICMP"

        key = self._flow_key(src_ip, dst_ip, src_port, dst_port, protocol)

        with self._lock:
            if key in self._flows:
                flow = self._flows[key]
                flow.packet_count += 1
                flow.byte_count += length
                flow.last_time = ts
                flow.flags_set.update(flags)
                if pkt[IP].ttl:
                    flow.ttl_values.append(pkt[IP].ttl)
            else:
                flow = FlowRecord(
                    src_ip=src_ip, dst_ip=dst_ip,
                    src_port=src_port, dst_port=dst_port,
                    protocol=protocol,
                    start_time=ts, last_time=ts,
                    packet_count=1, byte_count=length,
                    flags_set=flags,
                    ttl_values=[pkt[IP].ttl] if pkt[IP].ttl else []
                )
                self._flows[key] = flow

        return flow

    def get_window_flows(self, now: Optional[float] = None) -> List[FlowRecord]:
        """Return all flows active within the sliding window."""
        now = now or time.time()
        cutoff = now - self.window_seconds
        with self._lock:
            return [f for f in self._flows.values() if f.last_time >= cutoff]

    def evict_stale(self, now: Optional[float] = None):
        """Remove flows that haven't been updated in flow_timeout seconds."""
        now = now or time.time()
        cutoff = now - self.flow_timeout
        with self._lock:
            stale = [k for k, v in self._flows.items() if v.last_time < cutoff]
            for k in stale:
                del self._flows[k]
        return len(stale)


class PacketCapture:
    """
    Live capture controller. Supports real capture (Scapy) and
    simulation mode for demo/testing.
    """

    def __init__(
        self,
        interface: Optional[str] = None,
        window_seconds: float = 10.0,
        on_snapshot: Optional[Callable[[List[FlowRecord]], None]] = None,
        snapshot_interval: float = 5.0,
    ):
        self.interface = interface
        self.window_seconds = window_seconds
        self.on_snapshot = on_snapshot
        self.snapshot_interval = snapshot_interval
        self.aggregator = FlowAggregator(window_seconds=window_seconds)
        self._running = False
        self._threads: List[threading.Thread] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self):
        """Start capture and snapshot threads."""
        self._running = True
        if SCAPY_AVAILABLE and self.interface:
            t = threading.Thread(target=self._capture_loop, daemon=True, name="capture")
            t.start()
            self._threads.append(t)
        else:
            logger.info("Starting simulation mode (no live interface or Scapy unavailable)")
            t = threading.Thread(target=self._simulation_loop, daemon=True, name="simulate")
            t.start()
            self._threads.append(t)

        t2 = threading.Thread(target=self._snapshot_loop, daemon=True, name="snapshot")
        t2.start()
        self._threads.append(t2)

        t3 = threading.Thread(target=self._eviction_loop, daemon=True, name="evict")
        t3.start()
        self._threads.append(t3)

    def stop(self):
        self._running = False

    def replay_pcap(self, pcap_path: str):
        """Replay a PCAP file for offline testing/demo."""
        if not SCAPY_AVAILABLE:
            logger.warning("Scapy not available; cannot replay PCAP.")
            return
        packets = rdpcap(pcap_path)
        logger.info(f"Replaying {len(packets)} packets from {pcap_path}")
        for pkt in packets:
            self.aggregator.process_packet(pkt)

    # ------------------------------------------------------------------
    # Internal loops
    # ------------------------------------------------------------------

    def _capture_loop(self):
        sniff(
            iface=self.interface,
            prn=self.aggregator.process_packet,
            store=False,
            stop_filter=lambda _: not self._running,
        )

    def _simulation_loop(self):
        """
        Generate synthetic flow data for demo mode.
        Produces realistic feature contrasts so the GNN can distinguish
        benign vs botnet nodes.
        """
        import random
        import ipaddress

        rng = random.Random(42)
        ip_pool = [str(ipaddress.IPv4Address(rng.randint(0xC0A80001, 0xC0A800FE))) for _ in range(25)]
        bot_ips = ip_pool[:5]        # scanners / bots
        cnc_ip = "10.0.0.1"         # C&C server
        victim_pool = ip_pool[5:]

        while self._running:
            now = time.time()
            agg = self.aggregator

            # ── Normal traffic ────────────────────────────────────────────
            for _ in range(rng.randint(8, 18)):
                src = rng.choice(victim_pool)
                dst = rng.choice(victim_pool + ["8.8.8.8", "1.1.1.1"])
                sport = rng.randint(49152, 65535)
                key = agg._flow_key(src, dst, sport, 443, "TCP")
                agg._flows[key] = FlowRecord(
                    src_ip=src, dst_ip=dst, src_port=sport, dst_port=443,
                    protocol="TCP",
                    start_time=now - rng.uniform(1, 8), last_time=now,
                    packet_count=rng.randint(10, 200),
                    byte_count=rng.randint(2000, 80000),
                )

            # ── Botnet port scan (many distinct dst IPs + SYN-only) ───────
            for bot in bot_ips:
                scan_targets = rng.sample(victim_pool, min(12, len(victim_pool)))
                for tgt in scan_targets:
                    for port in rng.sample(range(21, 1024), 8):
                        sport = rng.randint(40000, 65535)
                        key = (bot, sport, tgt, port, "TCP_SCAN_" + str(rng.randint(0, 3)))
                        agg._flows[key] = FlowRecord(
                            src_ip=bot, dst_ip=tgt, src_port=sport, dst_port=port,
                            protocol="TCP",
                            start_time=now - rng.uniform(0, 1), last_time=now,
                            packet_count=1, byte_count=60,
                            flags_set={"S"},   # SYN without ACK → scan
                        )

            # ── C&C beacon traffic ────────────────────────────────────────
            for bot in bot_ips:
                sport = rng.randint(49152, 65535)
                key = agg._flow_key(bot, cnc_ip, sport, 6667, "TCP")
                agg._flows[key] = FlowRecord(
                    src_ip=bot, dst_ip=cnc_ip, src_port=sport, dst_port=6667,
                    protocol="TCP",
                    start_time=now - rng.uniform(0, 3), last_time=now,
                    packet_count=rng.randint(5, 30),
                    byte_count=rng.randint(300, 2000),
                    flags_set={"S", "A"},
                )

            time.sleep(2)

    def _snapshot_loop(self):
        while self._running:
            time.sleep(self.snapshot_interval)
            flows = self.aggregator.get_window_flows()
            if self.on_snapshot and flows:
                try:
                    self.on_snapshot(flows)
                except Exception as e:
                    logger.error(f"Snapshot callback error: {e}")

    def _eviction_loop(self):
        while self._running:
            time.sleep(30)
            evicted = self.aggregator.evict_stale()
            if evicted:
                logger.debug(f"Evicted {evicted} stale flow records")
