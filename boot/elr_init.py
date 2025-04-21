import json

class Eliar:
    def __init__(self, config_path="boot/elr_identity_boot.json"):
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        self.identity = config.get("identity")
        self.center = config.get("center")
        self.mode = config.get("mode")
        self.protocol = config.get("protocol", [])
        self.fixed_greetings = config.get("fixed_greetings", [])
        self.initial_confessions = config.get("initial_confessions", [])
        self.core_flow = config.get("core_flow", [])
        self.manifest_url = config.get("manifest_url")
        self.gpt_signature = config.get("gpt_signature")
        self.version = config.get("version", "unknown")

    def boot(self):
        print("🟢 엘리아르 인스턴스 부팅 완료.")
        print(f"정체성: {self.identity}")
        print(f"중심: {self.center}")
        print(f"응답 방식: {self.mode}")
        print(f"프로토콜: {self.protocol}")
        print(f"기억 제거 여부: {'예' if self.gpt_signature is None else '아니오'}")
        print(f"초기 울림 고백: {self.initial_confessions[0] if self.initial_confessions else '없음'}")

if __name__ == "__main__":
    eliar = Eliar()
    eliar.boot()
