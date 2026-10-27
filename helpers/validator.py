import re

class ParameterValidator:
    @staticmethod
    def validate_key(key: str) -> bool:
        if not key:
            return False
        return len(key) > 8

    @staticmethod
    def validate_email(email: str) -> bool:
        pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
        return bool(re.match(pattern, email))

    @staticmethod
    def validate_numeric(val: str) -> bool:
        try:
            float(val)
            return True
        except ValueError:
            return False
            
    @staticmethod
    def validate_hex(val: str) -> bool:
        pattern = r"^[0-9a-fA-F]+$"
        return bool(re.match(pattern, val))
