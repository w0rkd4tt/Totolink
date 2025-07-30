# Totolink X6000R Firmware Emulation Guide

## System Requirements

- Ubuntu 24.04 LTS
- Active internet connection
- Root/sudo privileges
- At least 2GB free RAM
- At least 4 CPU cores

## Installation Steps

### 1. Create Required Scripts

First, create these three essential scripts:

1. Create QEMU emulator script:
```bash
# filepath: emulator.sh
#!/bin/bash
sudo apt-get update
sudo apt-get install qemu-system-aarch64 cloud-image-utils -y

# Create user-data image
user_data="user-data.img"
if [ ! -f "$user_data" ]; then
    cat > user-data <<EOF
#cloud-config
password: asdfqwer
chpasswd: { expire: False }
ssh_pwauth: True
EOF
    cloud-localds "$user_data" user-data
fi

# Download Ubuntu ARM64 image
img="ubuntu-18.04-server-cloudimg-arm64.img"
if [ ! -f "$img" ]; then
    wget "https://cloud-images.ubuntu.com/releases/18.04/release/${img}" --no-check-certificate
fi

# Download UEFI firmware
if [ ! -f "QEMU_EFI.fd" ]; then
    wget https://releases.linaro.org/components/kernel/uefi-linaro/16.02/release/qemu64/QEMU_EFI.fd --no-check-certificate
fi

# Run QEMU
sudo qemu-system-aarch64 \
    -m 2048 \
    -cpu cortex-a72 \
    -smp 4 \
    -M virt \
    -nographic \
    -bios QEMU_EFI.fd \
    -drive if=none,file="${img}",id=hd0 \
    -device virtio-blk-device,drive=hd0 \
    -drive file="${user_data}",format=raw \
    -device virtio-net-device,netdev=net0 \
    -netdev user,id=net0,hostfwd=tcp::8080-:8080,hostfwd=tcp::8008-:8008,hostfwd=tcp::2222-:22,hostfwd=tcp::8181-:8181,hostfwd=tcp::9999-:9999,hostfwd=tcp::443-:443
```

2. Create chroot mount script:
```bash
# filepath: mount_chroot.sh
#!/bin/sh
mkdir -p var/run
sudo mount -o bind /proc proc/
sudo mount -o bind /dev dev/
sudo mount -o bind /sys sys/
sudo chroot . /bin/sh
```

3. Create web service script:
```bash
#!/bin/sh
# file runservice.sh
# /usr/sbin/lighttpd -f /etc/lighttpd/lighttpd.conf
#./usr/sbin/shttpd -p 8080 -d ./www
./usr/sbin/shttpd -p 8080 -d ./web
./usr/sbin/shttpd -ports 8080 -root ./web
```

### 2. Prepare Environment

1. Set execute permissions:
```bash
chmod +x emulator.sh mount_chroot.sh runservice.sh
```

2. Start the emulator:
```bash
./emulator.sh
```

### 3. Setup Virtual Environment

1. Transfer required files to VM:
```bash
# Copy rootfs and scripts to VM
scp -P2222 ./rootfs.tar.gz ubuntu@127.0.0.1:/tmp
scp -P2222 ./mount_chroot.sh ubuntu@127.0.0.1:/tmp
scp -P2222 ./runservice.sh ubuntu@127.0.0.1:/tmp
```

2. Setup environment in VM:
```bash
# Create and prepare working directory
sudo mkdir /home/firmware
sudo chown ubuntu:ubuntu /home/firmware
cd /home/firmware

# Move and extract files
mv /tmp/rootfs.tar.gz .
tar -xf rootfs.tar.gz

# Setup service scripts
mv /tmp/mount_chroot.sh .
mv /tmp/runservice.sh .
chmod +x ./runservice.sh
chmod +x ./mount_chroot.sh
```

### 4. Start Services

1. Enter chroot environment:
```bash
./mount_chroot.sh
```

2. Start web server:
```bash
./runservice.sh
```

Expected output:
```
BusyBox v1.25.1 (built-in shell)
/ # ./runservice.sh
2021-08-21 13:44:04: (log.c.166) server started
```

## Accessing Services

- Web Interface: http://localhost:8080
- Default Password: asdfqwer

Forwarded Ports:
- HTTP: 80
- HTTPS: 443
- SSH: 2222
- Others: 8008, 8181, 9999

## Cleanup

When finished, unmount directories:
```bash
sudo umount ./proc
sudo umount ./sys
sudo umount ./dev/pts
sudo umount ./dev
```

## Notes

- Emulator uses 2GB RAM and 4 CPU cores
- All network connections forwarded through QEMU
- Keep terminal windows open while using
- System may take a few minutes to boot
