#!/usr/bin/env bash
# Remove only l05 namespaces and root links; no other labs impacted.
set -u
[[ $EUID == 0 ]] || { echo 'sudo required'; exit 1; }
for ns in l05pc1 l05pc2 l05pc3 l05pc4 l05atk l05swa l05swb; do
  ip netns del "$ns" 2>/dev/null || true
done
ip link del l05ab 2>/dev/null || true
for p in l05brA l05brB; do ip link del "$p" 2>/dev/null || true; done
echo 'Lab05 cleaned'
