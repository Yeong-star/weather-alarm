import requests
import json
import os
from datetime import datetime, timedelta


def get_weather_forecast(service_key):
    """기상청 단기예보 API로 서울 날씨 정보 조회"""
    # 서울 중구 기준 격자 좌표
    nx, ny = 60, 127

    now = datetime.now()
    # 단기예보 발표시각: 0200, 0500, 0800, 1100, 1400, 1700, 2000, 2300
    # 오전 6:30 실행이므로 0500 발표 데이터 사용
    base_date = now.strftime("%Y%m%d")
    base_time = "0500"

    # 0500 이전이면 전날 2300 데이터 사용
    if now.hour < 6:
        yesterday = now - timedelta(days=1)
        base_date = yesterday.strftime("%Y%m%d")
        base_time = "2300"

    url = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
    params = {
        "serviceKey": service_key,
        "pageNo": "1",
        "numOfRows": "300",
        "dataType": "JSON",
        "base_date": base_date,
        "base_time": base_time,
        "nx": nx,
        "ny": ny,
    }

    response = requests.get(url, params=params)
    data = response.json()

    items = data["response"]["body"]["items"]["item"]

    # 오늘 날씨 정보 정리
    forecast = {}
    today = now.strftime("%Y%m%d")

    for item in items:
        if item["fcstDate"] != today:
            continue
        category = item["category"]
        time = item["fcstTime"]
        value = item["fcstValue"]

        if time not in forecast:
            forecast[time] = {}
        forecast[time][category] = value

    return forecast


def parse_weather(forecast):
    """날씨 데이터를 읽기 쉬운 메시지로 변환"""
    # 카테고리 코드 설명
    sky_code = {"1": "맑음", "3": "구름많음", "4": "흐림"}
    pty_code = {"0": "없음", "1": "비", "2": "비/눈", "3": "눈", "4": "소나기"}

    temps = []
    rain_expected = False
    snow_expected = False
    rain_probs = []
    sky_status = []

    morning_times = ["0600", "0700", "0800", "0900"]
    afternoon_times = ["1200", "1300", "1400", "1500"]
    evening_times = ["1800", "1900", "2000", "2100"]

    for time, data in sorted(forecast.items()):
        # 기온 (TMP)
        if "TMP" in data:
            temps.append(int(data["TMP"]))

        # 강수 확률 (POP)
        if "POP" in data:
            rain_probs.append(int(data["POP"]))

        # 강수 형태 (PTY)
        if "PTY" in data and data["PTY"] != "0":
            if data["PTY"] in ("1", "4"):
                rain_expected = True
            elif data["PTY"] in ("2", "3"):
                snow_expected = True

        # 하늘 상태 (SKY)
        if "SKY" in data:
            sky_status.append(data["SKY"])

    # 시간대별 기온
    morning_temps = []
    afternoon_temps = []
    evening_temps = []
    for time, data in sorted(forecast.items()):
        if "TMP" in data:
            if time in morning_times:
                morning_temps.append(int(data["TMP"]))
            elif time in afternoon_times:
                afternoon_temps.append(int(data["TMP"]))
            elif time in evening_times:
                evening_temps.append(int(data["TMP"]))

    # 대표 하늘 상태
    if sky_status:
        from collections import Counter
        most_common_sky = Counter(sky_status).most_common(1)[0][0]
        sky_text = sky_code.get(most_common_sky, "알 수 없음")
    else:
        sky_text = "정보 없음"

    # 메시지 구성
    today_str = datetime.now().strftime("%m월 %d일 (%a)")
    day_names = {"Mon": "월", "Tue": "화", "Wed": "수", "Thu": "목", "Fri": "금", "Sat": "토", "Sun": "일"}
    for eng, kor in day_names.items():
        today_str = today_str.replace(eng, kor)

    min_temp = min(temps) if temps else "?"
    max_temp = max(temps) if temps else "?"
    max_rain_prob = max(rain_probs) if rain_probs else 0

    msg = f"🌤 {today_str} 서울 날씨\n"
    msg += f"━━━━━━━━━━━━━━━\n"
    msg += f"🌡 기온: {min_temp}°C ~ {max_temp}°C\n"
    msg += f"☁ 하늘: {sky_text}\n"
    msg += f"🌧 강수확률: {max_rain_prob}%\n"

    if morning_temps:
        msg += f"\n🌅 오전: {min(morning_temps)}~{max(morning_temps)}°C"
    if afternoon_temps:
        msg += f"\n☀ 오후: {min(afternoon_temps)}~{max(afternoon_temps)}°C"
    if evening_temps:
        msg += f"\n🌙 저녁: {min(evening_temps)}~{max(evening_temps)}°C"

    # 우산 필요 여부
    msg += f"\n\n━━━━━━━━━━━━━━━\n"
    if rain_expected:
        msg += "☂ 우산을 꼭 챙기세요! 비 예보가 있습니다.\n"
    elif max_rain_prob >= 40:
        msg += "☂ 우산을 챙기세요! 강수확률이 높습니다.\n"
    elif max_rain_prob >= 20:
        msg += "🌂 접이식 우산을 챙기면 좋겠어요.\n"
    else:
        msg += "☀ 우산은 필요 없어요!\n"

    if snow_expected:
        msg += "❄ 눈 예보가 있습니다. 외출 시 주의하세요!\n"

    # 옷차림 추천
    if temps:
        avg_temp = sum(temps) / len(temps)
        msg += "\n👔 옷차림: "
        if avg_temp <= 4:
            msg += "패딩, 두꺼운 코트, 목도리"
        elif avg_temp <= 8:
            msg += "코트, 가죽자켓, 히트텍"
        elif avg_temp <= 11:
            msg += "자켓, 트렌치코트, 니트"
        elif avg_temp <= 16:
            msg += "가디건, 얇은 자켓, 맨투맨"
        elif avg_temp <= 19:
            msg += "얇은 니트, 긴팔, 가디건"
        elif avg_temp <= 22:
            msg += "긴팔, 얇은 가디건"
        elif avg_temp <= 27:
            msg += "반팔, 얇은 셔츠, 반바지"
        else:
            msg += "민소매, 반팔, 반바지"

    return msg


def refresh_kakao_token(rest_api_key, client_secret, refresh_token):
    """Refresh Token으로 Access Token 갱신"""
    url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": rest_api_key,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
    }
    response = requests.post(url, data=data)
    result = response.json()
    return result


def send_kakao_message(access_token, message):
    """카카오톡 나에게 보내기"""
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {"Authorization": f"Bearer {access_token}"}

    template = {
        "object_type": "text",
        "text": message,
        "link": {
            "web_url": "https://weather.naver.com",
            "mobile_web_url": "https://weather.naver.com",
        },
        "button_title": "날씨 자세히 보기",
    }

    data = {"template_object": json.dumps(template)}
    response = requests.post(url, headers=headers, data=data)
    return response.json()


def main():
    # 환경변수에서 키 읽기
    weather_api_key = os.environ["WEATHER_API_KEY"]
    kakao_rest_key = os.environ["KAKAO_REST_KEY"]
    kakao_client_secret = os.environ["KAKAO_CLIENT_SECRET"]
    kakao_refresh_token = os.environ["KAKAO_REFRESH_TOKEN"]

    # 1. Access Token 갱신
    token_result = refresh_kakao_token(kakao_rest_key, kakao_client_secret, kakao_refresh_token)

    if "access_token" not in token_result:
        print(f"토큰 갱신 실패: {token_result}")
        return

    access_token = token_result["access_token"]

    # Refresh Token이 갱신된 경우 출력 (GitHub Actions에서 수동 업데이트 필요 알림)
    if "refresh_token" in token_result:
        print(f"⚠ Refresh Token이 갱신되었습니다. GitHub Secrets를 업데이트하세요.")
        print(f"새 Refresh Token: {token_result['refresh_token']}")

    # 2. 날씨 정보 조회
    try:
        forecast = get_weather_forecast(weather_api_key)
        message = parse_weather(forecast)
    except Exception as e:
        message = f"⚠ 날씨 정보 조회 실패: {str(e)}"

    # 3. 카카오톡 전송
    result = send_kakao_message(access_token, message)
    print(f"전송 결과: {result}")
    print(message.encode("utf-8", errors="replace").decode("utf-8"))


if __name__ == "__main__":
    main()
