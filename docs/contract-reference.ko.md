# 계약 참조 문서

이 문서는 계약 스키마 버전 `1`을 설명합니다. 편집기에서는 `schema/skill-contract.schema.json`을 이용해 기본 구조를 검사할 수 있습니다. 실제 판정은 CLI 구현을 기준으로 합니다.

## 계약 탐색과 경로 규칙

`skill-contract check <path>`에는 계약 파일 하나 또는 디렉터리를 전달할 수 있습니다. 디렉터리를 검사하면 하위의 `skill-contract.yaml`, `skill-contract.yml`, `skill-contract.json`을 자동으로 찾습니다. 일반적인 의존성 디렉터리와 캐시 디렉터리는 건너뜁니다.

## 편집기 설정

저장소에 포함된 스키마를 연결하면 `skill-contract.yaml`을 편집할 때 자동 완성과 유효성 검사를 사용할 수 있습니다.

### VS Code

복제한 저장소 안에 전역 설정이 아닌 워크스페이스 설정으로 `.vscode/settings.json`을 만듭니다.

```json
{
  "yaml.schemas": {
    "./schema/skill-contract.schema.json": ["skill-contract.yaml", "skill-contract.yml"]
  }
}
```

`yaml.schemas`를 지원하는 YAML 확장을 설치한 다음 계약 파일을 엽니다. `2`와 같은 잘못된 `version` 값이나 `{ "regex": 42 }`와 같은 잘못된 패턴 객체가 표시되어야 합니다.

### JetBrains IDE

JetBrains IDE에서 **Settings | Languages & Frameworks | Schemas and DTDs | JSON Schema Mappings**를 열고 프로젝트 매핑을 추가한 뒤, 복제한 저장소의 `schema/skill-contract.schema.json`을 선택합니다. 파일 패턴으로 `skill-contract.yaml`과 `skill-contract.yml`을 추가합니다. 같은 잘못된 `version`과 패턴 예제가 편집기에 표시되어야 합니다.

전체 필드 동작은 [JSON Schema](../schema/skill-contract.schema.json)를 참고하세요.

계약 안의 모든 경로는 상대 경로여야 합니다. 계약 디렉터리를 기준으로 해석하며, 그 디렉터리 밖으로 나갈 수 없습니다. 규칙 대상, 필수 파일, 참고 파일, 참고 문서를 언급해야 하는 파일도 선택한 스킬 디렉터리 안에 있어야 합니다.

## 최상위 필드

### `version`

필수 필드입니다. 현재는 `1`만 지원합니다.

### `skill`

선택 필드입니다. 계약 디렉터리에서 스킬 디렉터리까지의 상대 경로를 적습니다. 기본값은 `.`입니다.

### `rules`

문구를 검사하는 규칙 목록입니다. 각 규칙에는 다음 필드를 사용할 수 있습니다.

- `id`: `^[a-z0-9][a-z0-9._-]*$` 형식을 따르는 고유 식별자입니다.
- `description`: 사람이 이해할 수 있는 규칙 설명입니다.
- `target`: 검사할 상대 경로이며, 기본값은 `SKILL.md`입니다.
- `require.all`: 목록에 있는 모든 패턴이 일치해야 합니다.
- `require.any`: 목록에 있는 패턴 중 하나 이상이 일치해야 합니다.
- `forbid`: 목록에 있는 패턴이 하나도 일치하면 안 됩니다.

문자열을 바로 적으면 일반 문구로 검사합니다. 정규식과 대소문자 구분이 필요하면 객체를 사용합니다.

```yaml
rules:
  - id: approval-gate
    require:
      all:
        - explicit approval
        - regex: stop\s+when\s+approval\s+is\s+absent
          case_sensitive: false
```

일반 문구와 정규식은 기본적으로 대소문자를 구분하지 않습니다. 대소문자가 규칙의 일부라면 `case_sensitive: true`를 지정합니다.

### `files.required`

스킬 디렉터리 안에 반드시 있어야 하는 파일을 적습니다.

```yaml
files:
  required:
    - scripts/check.py
    - references/safety.md
```

### `references.required`

각 파일은 실제로 존재해야 하며 지정된 문서에서도 경로가 언급되어야 합니다. 문자열만 적으면 `SKILL.md`에서 언급했는지 확인합니다. 다른 문서에서 언급해야 한다면 객체를 사용합니다.

```yaml
references:
  required:
    - references/safety.md
    - path: scripts/validate.py
      mentioned_in: references/implementation.md
```

이 검사는 경로 문자열을 직접 비교하며, 경로 구분자 차이는 허용합니다. 문서 사이의 의미 관계를 추론하지는 않습니다.

### `frontmatter`

`SKILL.md`의 필수 메타데이터와 도구 선언을 검사합니다.

```yaml
frontmatter:
  required_fields: [name, description]
  required_tools: [Read, Bash]
```

도구 선언은 `allowed-tools`와 `allowed_tools`를 모두 인식합니다. 공백이나 쉼표로 구분한 문자열과 YAML 목록을 사용할 수 있습니다. `Bash(git:*)`처럼 범위를 붙인 선언도 `Bash` 요구사항을 충족합니다.

### `portability`

이식성 검사는 기본적으로 켜져 있습니다. 해당 계약에서 사용하지 않으려면 `portability: false`로 지정합니다.

```yaml
portability:
  forbid_personal_paths: true
  allow_external_symlinks: false
  scan:
    - SKILL.md
    - references/**/*.md
    - scripts/**/*
  exclude:
    - references/generated/**
  allow:
    - regex: /home/example-user/\S+
```

`forbid_personal_paths`는 Windows와 macOS의 `Users`, Linux의 `home` 아래에 있는 사용자별 경로를 찾습니다. CI 로그를 통해 경로가 다시 노출되지 않도록 실제로 일치한 문자열은 결과에 표시하지 않습니다.

`allow`는 검토를 마친 합성 실패 자료에만 사용해야 합니다. 허용 범위를 넓게 잡으면 실제 이식성 문제를 놓칠 수 있습니다.

외부 심볼릭 링크는 새로 복제한 저장소에 필요한 파일이 없을 수 있으므로 기본적으로 허용하지 않습니다. 끊어진 심볼릭 링크는 설정과 관계없이 오류로 처리합니다.

## 확장 필드

알 수 없는 필드는 설정 오류로 처리합니다. 다만 최상위 또는 개별 규칙에서 이름이 `x-`로 시작하는 필드는 로컬 메타데이터를 위한 확장 필드로 보고 무시합니다.

## 종료 코드

| 코드 | 의미 |
| ---: | --- |
| `0` | 발견한 모든 계약이 통과했습니다. |
| `1` | 유효한 계약에서 하나 이상의 위반 사항을 발견했습니다. |
| `2` | 명령, 경로, 문법, 계약 설정에 문제가 있습니다. |

## 출력 형식

`text`는 터미널에서 읽기 위한 형식입니다. `json`은 스키마 버전 `1`을 사용하는 기계 판독 형식입니다. `github`는 일치한 원문을 노출하지 않고 GitHub Actions 주석을 출력합니다.
