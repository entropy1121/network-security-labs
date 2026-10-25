# SW2 ONLY; after baseline attack, and after bridge is configured.
# Ensure no duplicate LAB03_ALLOW/DROP rules before running these commands.
/interface bridge port set [find where interface=ether4] learn=no
/interface bridge host add bridge=br-lab interface=ether4 mac-address=02:33:03:00:00:39
/interface bridge filter add chain=forward in-interface=ether4 src-mac-address=02:33:03:00:00:39/FF:FF:FF:FF:FF:FF action=accept comment=LAB03_ALLOW
/interface bridge filter add chain=forward in-interface=ether4 action=drop comment=LAB03_DROP_SPOOF
/interface bridge filter print stats
/interface bridge port print detail where interface=ether4
/interface bridge host print where on-interface=ether4
