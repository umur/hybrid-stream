#!/usr/bin/env bash
# Apply tc netem network profile. Usage: ./setup_netem.sh N1|N2|N3 [interface]
set -euo pipefail
PROFILE="${1:-N1}"; INTERFACE="${2:-eth0}"

case "$PROFILE" in
    N1) DELAY="5ms"  JITTER="1ms"  RATE="1000mbit" ;;
    N2) DELAY="25ms" JITTER="5ms"  RATE="100mbit"  ;;
    N3) DELAY="75ms" JITTER="15ms" RATE="50mbit"   ;;
    *)  echo "Unknown profile: $PROFILE (use N1, N2, or N3)"; exit 1 ;;
esac

echo "Applying $PROFILE to $INTERFACE: delay=$DELAY±$JITTER bw=$RATE"
tc qdisc del dev "$INTERFACE" root 2>/dev/null || true
tc qdisc add dev "$INTERFACE" root netem delay "$DELAY" "$JITTER" rate "$RATE"
echo "Done."
