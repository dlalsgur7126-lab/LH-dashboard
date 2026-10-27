import requests
from bs4 import BeautifulSoup
import schedule
import time
import json
from datetime import datetime
import os

# OpenAI API를 사용하기 위한 라이브러리입니다. (설치: pip install openai)
# 텍스트 마이닝(감성 분석, 토픽 모델링) 역할을 수행합니다.
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# ==========================================
# ⚙️ 설정 (Configuration)
# ==========================================
# 발급받은 OpenAI API 키를 여기에 입력하세요. (없으면 테스트용 가짜 데이터가 생성됩니다.)
OPENAI_API_KEY = "YOUR_OPENAI_API_KEY" 
SEARCH_KEYWORD = "한국토지주택공사"
TARGET_TIME = "21:00" # 매일 밤 9시 실행

# 웹 브라우저인 척 위장하여 네이버의 봇 차단을 우회하기 위한 헤더
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
}

def crawl_naver_news(keyword):
    """
    네이버 뉴스 검색결과 첫 페이지에서 기사 제목과 요약 내용을 긁어옵니다.
    """
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🔍 '{keyword}' 뉴스 크롤링을 시작합니다...")
    
    url = f"https://search.naver.com/search.naver?where=news&query={keyword}"
    response = requests.get(url, headers=HEADERS)
    
    # 크롤링 결과를 담을 리스트
    news_list = []
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        # 네이버 뉴스 검색 결과의 기사 영역(list_news) 찾기
        articles = soup.select('.list_news > li')
        
        for article in articles:
            # 기사 제목 추출
            title_tag = article.select_one('.news_tit')
            # 기사 요약(snippet) 추출
            snippet_tag = article.select_one('.news_dsc')
            
            if title_tag and snippet_tag:
                title = title_tag.text.strip()
                link = title_tag['href']
                snippet = snippet_tag.text.strip()
                
                news_list.append({
                    "title": title,
                    "link": link,
                    "snippet": snippet
                })
        
        print(f"✅ 총 {len(news_list)}개의 기사를 성공적으로 수집했습니다.")
        return news_list
    else:
        print(f"❌ 웹 페이지를 불러오는 데 실패했습니다. (상태 코드: {response.status_code})")
        return []

def analyze_news_with_ai(news_list):
    """
    수집된 뉴스 데이터를 OpenAI(LLM)에 보내어 기회(Opportunity)와 위협(Threat) 요인으로 분류 및 요약합니다.
    (전략적기획론 6주차: 감성 분석 및 토픽 모델링 기법 적용)
    """
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🧠 AI 텍스트 마이닝 분석을 시작합니다...")
    
    if not news_list:
        return {"error": "수집된 뉴스가 없습니다."}

    # 뉴스 텍스트 하나로 뭉치기 (AI에게 프롬프트로 전달하기 위함)
    combined_text = "\n".join([f"- {news['title']}: {news['snippet']}" for news in news_list])
    
    # OpenAI API 키가 설정되지 않은 경우를 위한 방어 로직 (테스트 모드)
    if OPENAI_API_KEY == "YOUR_OPENAI_API_KEY" or OpenAI is None:
        print("⚠️ OpenAI API 키가 입력되지 않았거나 패키지가 설치되지 않았습니다. [테스트 모드]로 가상 분석 결과를 반환합니다.")
        time.sleep(2) # 분석하는 척 대기
        return {
            "update_time": datetime.now().strftime('%Y-%m-%d %H:%M'),
            "summary": "오늘 LH와 관련된 긍정/부정 이슈가 혼재되어 나타났습니다.",
            "opportunities": [
                "주택공급 확대 정책에 따른 공공시행 물량 증가 기대",
                "신규 스마트시티 및 주거복지 사업 모델 호평"
            ],
            "threats": [
                "원자재가 상승으로 인한 건설 공사비 압박 지속",
                "일부 지역 주민들의 보상 관련 민원 제기"
            ],
            "raw_news_count": len(news_list)
        }

    # 실제 OpenAI API를 사용한 분석 로직
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        system_prompt = """
        당신은 전략적 기획 및 거시환경(PEST), SWOT 분석의 최고 전문가입니다.
        제공되는 뉴스 기사들을 분석하여 다음의 JSON 형식으로만 응답해주세요:
        {
            "summary": "전체 뉴스를 1~2줄로 요약",
            "opportunities": ["기회 요인 1", "기회 요인 2"],
            "threats": ["위기/위협 요인 1", "위기/위협 요인 2"]
        }
        """
        
        response = client.chat.completions.create(
            model="gpt-4o-mini", # 저렴하고 빠른 모델 사용
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": combined_text}
            ],
            response_format={ "type": "json_object" } # JSON 형태로 확실히 받기
        )
        
        # AI의 응답(JSON 문자열)을 파이썬 딕셔너리로 변환
        result_data = json.loads(response.choices[0].message.content)
        result_data["update_time"] = datetime.now().strftime('%Y-%m-%d %H:%M')
        result_data["raw_news_count"] = len(news_list)
        
        print("✅ AI 분석 완료!")
        return result_data
        
    except Exception as e:
        print(f"❌ AI 분석 중 오류 발생: {e}")
        return {"error": str(e)}

def save_to_json(data, filename="lh_daily_report.json"):
    """
    분석된 결과를 HTML 대시보드에서 읽어갈 수 있도록 JSON 파일로 저장합니다.
    """
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"💾 분석 결과가 '{filename}' 파일로 저장되었습니다.\n")

def daily_crawling_job():
    """
    스케줄러에 의해 매일 특정 시간에 실행될 전체 작업 흐름(Pipeline)
    """
    print("\n" + "="*50)
    print(f"🚀 자동화 작업 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*50)
    
    # 1. 크롤링 (Data Gathering)
    news_data = crawl_naver_news(SEARCH_KEYWORD)
    
    # 2. 텍스트 마이닝 및 전략 분석 (Data Analysis)
    analysis_result = analyze_news_with_ai(news_data)
    
    # 3. 데이터 저장 (Dashboard Sync)
    save_to_json(analysis_result)

if __name__ == "__main__":
    # 처음 실행 시 즉시 한 번 작동시켜서 결과를 확인합니다.
    daily_crawling_job()
    
    # 스케줄러 등록 (매일 지정된 시간에 실행)
    schedule.every().day.at(TARGET_TIME).do(daily_crawling_job)
    
    print(f"⏰ 스케줄러가 가동되었습니다. 매일 [{TARGET_TIME}]에 자동으로 뉴스를 수집하고 분석합니다.")
    print("프로그램을 종료하려면 Ctrl+C를 누르세요.\n")
    
    # 무한 루프를 돌며 예약된 시간이 되었는지 1초마다 확인합니다.
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 스케줄러를 종료합니다. 수고하셨습니다!")