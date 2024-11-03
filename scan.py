import socket
import struct
import re
import time

def discover_onvif_devices(timeout=10):
    """使用 WS-Discovery 协议在局域网中查找支持 ONVIF 的设备"""
    multicast_group = ('239.255.255.250', 3702)
    found_devices = set()

    print("Discovering ONVIF devices on the local network...")

    # 创建并配置套接字
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.settimeout(timeout)

    # 设置多播 TTL (Time to Live) 及加入多播组
    ttl = struct.pack('b', 1)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
    mreq = struct.pack("4sl", socket.inet_aton(multicast_group[0]), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    # WS-Discovery Probe 消息
    message = '''<?xml version="1.0" encoding="UTF-8"?>
    <e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope"
                xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing"
                xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery"
                xmlns:dn="http://www.onvif.org/ver10/network/wsdl">
      <e:Header>
        <w:MessageID>uuid:1</w:MessageID>
        <w:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To>
        <w:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action>
      </e:Header>
      <e:Body>
        <d:Probe>
          <d:Types>dn:NetworkVideoTransmitter</d:Types>
        </d:Probe>
      </e:Body>
    </e:Envelope>'''

    try:
        # 发送探测请求到多播地址
        sock.sendto(message.encode('utf-8'), multicast_group)

        # 接收来自各设备的响应，直到超时结束
        while True:
            try:
                data, addr = sock.recvfrom(8192)
                ip_address = addr[0]

                # 记录未见过的设备
                if ip_address not in found_devices:
                    found_devices.add(ip_address)

                    # 提取设备地址信息
                    xaddrs = re.findall(r'http://[0-9]+(?:\.[0-9]+){3}:[0-9]+', data.decode('utf-8'))
                    if xaddrs:
                        print(f"ONVIF Device found at IP: {ip_address}, XAddrs: {xaddrs[0]}")
                    else:
                        print(f"ONVIF Device found at IP: {ip_address}")

            except socket.timeout:
                # 当超时发生，结束扫描
                print("Discovery finished.")
                break

    except Exception as e:
        print(f"Error during discovery: {e}")

    finally:
        # 移除多播组并清理套接字
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, mreq)
        sock.close()
        time.sleep(1)  # 增加延迟确保套接字资源释放

    if not found_devices:
        print("No ONVIF devices found on the network.")
    else:
        print(f"Total devices discovered: {len(found_devices)}")

if __name__ == "__main__":
    discover_onvif_devices()
