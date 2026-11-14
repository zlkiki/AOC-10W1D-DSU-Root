#!/system/bin/sh
# AOC 10W1D DSU diagnostics v2
# - keeps console loglevel at 8 so everything reaches ramoops
# - status every 30s for 8 min; at 150s tries to force USB adb
# - then warm reboot (ramoops preserved)
# Create /data/local/tmp/dsudiag_stop (adb root) to cancel the reboot.
lv() { echo 8 > /proc/sys/kernel/printk 2>/dev/null; }
k() { lv; echo "<2>DSUDIAG: $*" > /dev/kmsg; }
kp() { while read -r l; do echo "<2>DSUDIAG-$1: $l" > /dev/kmsg; done; }
k "v2 service start uptime=$(cut -d' ' -f1 /proc/uptime) enforce=$(getenforce 2>&1) printk=$(cat /proc/sys/kernel/printk)"
i=0
while [ $i -lt 16 ]; do
  sleep 30
  i=$((i+1)); t=$((i*30))
  k "t=${t}s usb.config=$(getprop sys.usb.config) usb.state=$(getprop sys.usb.state) usb.ffs=$(getprop sys.usb.ffs.ready) persist.usb=$(getprop persist.sys.usb.config) adbd=$(getprop init.svc.adbd) zygote=$(getprop init.svc.zygote) vold=$(getprop init.svc.vold) boot_completed=$(getprop sys.boot_completed)"
  k "t=${t}s udc_g1=[$(cat /config/usb_gadget/g1/UDC 2>&1)] udc_list=[$(ls /sys/class/udc 2>&1 | tr '\n' ' ')] udc_state=[$(cat /sys/class/udc/*/state 2>&1 | tr '\n' ' ')] data_mnt=[$(grep ' /data ' /proc/mounts | cut -d' ' -f1,3)]"
  if [ $t -eq 60 ] || [ $t -eq 240 ]; then
    k "--- init.svc snapshot t=${t}s ---"
    getprop | grep -E 'init\.svc\.|sys\.usb|vold\.|ro\.crypto|sys\.boot|init\.svc_debug' | kp P
    ps -A -o PID,PPID,S,WCHAN:24,NAME 2>/dev/null | grep -v -E ' \[|kworker|ksoftirq|migration|rcu_|cpuhp' | kp PS
    ls -l /config/usb_gadget/g1 /config/usb_gadget/g1/configs/b.1 2>&1 | kp G
  fi
  if [ $t -eq 150 ] && [ "$(getprop init.svc.adbd)" != "running" ]; then
    k "forcing USB adb: setprop sys.usb.config adb + start adbd"
    setprop sys.usb.config adb
    sleep 3
    start adbd
    sleep 5
    k "after force: usb.config=$(getprop sys.usb.config) usb.state=$(getprop sys.usb.state) adbd=$(getprop init.svc.adbd) udc_g1=[$(cat /config/usb_gadget/g1/UDC 2>&1)]"
  fi
  if [ -f /data/local/tmp/dsudiag_stop ]; then
    k "stop file found, reboot cancelled"
    exit 0
  fi
done
k "--- final getprop ---"
getprop | grep -E 'usb|adb|init\.svc\.|vold|crypto|boot' | kp P
k "--- logcat errors tail ---"
logcat -d -b main,system,crash -v brief '*:E' 2>/dev/null | tail -60 | kp LC
k "warm reboot now (ramoops preserved)"
sleep 2
setprop sys.powerctl reboot
