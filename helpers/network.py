import socket

class NetworkStatusHelper:
    @staticmethod
    def resolve_host(hostname: str) -> str:
        try:
            return socket.gethostbyname(hostname)
        except socket.gaierror:
            return ""

    @staticmethod
    def is_port_open(ip: str, port: int, timeout: int = 3) -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                return s.connect_ex((ip, port)) == 0
        except Exception:
            return False
            
    @staticmethod
    def check_dns(dns_server: str) -> bool:
        return bool(NetworkStatusHelper.resolve_host(dns_server))
