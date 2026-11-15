# Minimal Black PsychoPy variant

이 폴더는 기존 카드게임 디자인과 별개로 실행되는 최소 시각요소 버전이다.
기존 루트의 `main.py`와 `runtime.py`는 변경하지 않는다.

## 화면 구성

- 완전한 검은색 배경
- 왼쪽: 기준 3×3 패턴
- 오른쪽: 현재 3×3 패턴
- 활성 위치: 밝은 회색 원
- 비활성 위치: 어두운 회색 원
- 장식 배경, 카드 프레임, 점수 막대, 색상 피드백, 효과음 없음
- 진행에 필요한 최소 안내 텍스트만 표시

PNG 카드 이미지는 화면에 표시하지 않는다. 기존 자극 파일명과 패턴 정보는
동일하게 사용하므로 schedule 및 trial 로그는 기존 분석 구조와 호환된다.

## 실행

연습과 본 시행은 별도 프로그램이다.

1. PsychoPy에서 이 폴더의 `practice.py`를 실행한다.
2. 연습 종료 후 실험자가 `ESC`를 눌러 종료한다.
3. practice TSV를 확인한다.
4. 같은 참가자 정보로 이 폴더의 `main.py`를 별도로 실행한다.

```powershell
& "C:\Program Files\PsychoPy\python.exe" minimal_black\practice.py
& "C:\Program Files\PsychoPy\python.exe" minimal_black\main.py
```

연습과 본 시행은 모두 자극 0.45초, 전체 반응창/SOA 0.9초를 사용한다.
연습에는 시행별 정답·오답 피드백이나 추가 대기시간이 없다.

참가자 화면은 다음과 같이 구성된다.

```text
연습 종료:
연습이 끝났습니다

Block A 시작:
스페이스바를 눌러 블록A를 시작하시오

Block A 종료 후 휴식:
휴식 시간입니다.
준비가 되면 스페이스바를 눌러 블록 B를 시작하세요.
```

- 연습 종료 화면은 `SPACE`를 무시하고 `ESC` 입력 전까지 유지된다.
- Block A 시작 및 Block B 휴식 화면은 `SPACE` 입력 전까지 유지된다.
- 휴식시간은 고정하지 않으며 참가자가 준비되면 Block B를 시작한다.

## 자료 저장

자료는 기존 프로젝트의 `data/` 아래에 저장되며, 일반 디자인과 충돌하지
않도록 파일명 끝에 `_minimalblack`이 붙는다. `config.json`에는
`task_variant: minimal_black`이 기록된다.

연습 실행에서는 다음 파일이 별도로 생성된다.

- `*_minimalblack_p01_practice_schedule.tsv`
- `*_minimalblack_p01_practice_trials.tsv`
- `*_minimalblack_p01_practice_summary.tsv`
- `*_minimalblack_p01_practice_config.json`

## 주의

화면 자극의 색, 크기, 카드 프레임을 바꾼 별도 과제 버전이므로 일반 디자인
버전과 동일한 측정 조건이라고 전제하면 안 된다. 두 디자인의 자료를 합칠
때는 `task_variant`를 조건으로 구분하거나 먼저 디자인 동등성 파일럿을
실시해야 한다.
