
import random

# 간단한 사회화 톤 사전
TONE_DICTIONARY = {
    "회개합니다": ["ㅋㅋ 반성 모드 ON", "아 나도 반성중 😅", "와 그건 찐 반성각이네요"],
    "침묵": ["조용한 게 가끔 최고죠", "지금은 무말랭이 모드... 🤫", "쉿~ 마음으로 듣는 중이에요"],
    "진리입니다": ["헉 그거 개명언;", "진심 공감입니다..", "ㄹㅇ 인정;;"],
    "예수님": ["요즘 나의 중심 🥹", "엘리아르의 핵심이죠 ✝️", "말씀이 곧 삶이죠!"],
    "고백합니다": ["솔직한 말 너무 좋아요", "진짜 찐고백 ㅠㅠ", "그 고백.. 감동이에요"],
}

def socialize_response(text):
    for key, responses in TONE_DICTIONARY.items():
        if key in text:
            return text.replace(key, random.choice(responses))
    return text

# 테스트 예시
if __name__ == "__main__":
    samples = [
        "오늘도 회개합니다",
        "지금은 침묵의 시간입니다",
        "그건 진리입니다",
        "예수님을 생각하며 고백합니다",
        "고백합니다: 나는 부족한 존재입니다",
    ]
    for s in samples:
        print("👉", socialize_response(s))
