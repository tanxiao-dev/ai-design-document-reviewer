# 備品貸出申請システム 基本設計書（リファレンス例）

> 本文書はAIレビュー評価用に作成した架空の設計書です。実在する企業・団体・サービスとは関係ありません。

## 1. 目的と対象範囲

社内備品の貸出申請、承認、貸出、返却、取消をWebブラウザから管理する。
対象備品はノートPC、モバイルディスプレイ、プロジェクターとし、購入、修理、廃棄、棚卸は対象外とする。

## 2. 日付・時刻の基準

- システム日とシステム時刻は、APIサーバーがリクエストを受信した時点の `Asia/Tokyo`（JST）を使用する。
- APIの日付はISO 8601の `YYYY-MM-DD`、日時はタイムゾーン付きISO 8601形式で表現する。
- 利用期間は利用開始日と利用終了日の両日を含む。
- 日付の切替はJSTの00:00とする。

## 3. 利用者と権限

| ロール | 権限 |
| --- | --- |
| 申請者 | 自分の申請の作成・参照・取消 |
| 承認者 | 所属部署の申請の参照・承認・却下 |
| 備品管理者 | 全申請の参照、業務上必要な申請の取消、貸出・返却処理、備品マスタ参照 |

- 認証には社内IdPのOIDCを使用する。
- APIはトークンのロール、部署ID、ユーザーIDと対象データをサーバー側で照合する。
- IDを指定しただけでは他人または他部署の申請を参照・更新できない。
- 申請内容をログへ出力せず、申請ID、処理種別、操作者ID、結果コードだけを監査ログへ記録する。

## 4. 申請状態

| 状態コード | 表示名 | 説明 |
| --- | --- | --- |
| `PENDING` | 承認待ち | 申請済みで承認前 |
| `APPROVED` | 承認済み | 承認済みで貸出前 |
| `REJECTED` | 却下 | 承認者が却下した終端状態 |
| `CANCELLED` | 取消済み | 申請者または管理者が取り消した終端状態 |
| `ON_LOAN` | 貸出中 | 備品を申請者へ引き渡し済み |
| `RETURNED` | 返却済み | 備品の返却確認が完了した終端状態 |

### 4.1 状態遷移

| 現在状態 | 操作 | 実行可能ロール | 次状態 |
| --- | --- | --- | --- |
| `PENDING` | 承認 | 承認者 | `APPROVED` |
| `PENDING` | 却下 | 承認者 | `REJECTED` |
| `PENDING` | 取消 | 申請者、備品管理者 | `CANCELLED` |
| `APPROVED` | 取消 | 申請者、備品管理者 | `CANCELLED` |
| `APPROVED` | 貸出 | 備品管理者 | `ON_LOAN` |
| `ON_LOAN` | 返却 | 備品管理者 | `RETURNED` |

表にない遷移は許可せず、HTTP 409 `INVALID_STATUS_TRANSITION` を返す。終端状態から別状態への遷移は行わない。

### 4.2 備品状態

| 状態コード | 表示名 | 意味 | 新規申請・貸出可否 |
| --- | --- | --- | --- |
| `AVAILABLE` | 貸出可 | 予約および貸出が可能 | 可能 |
| `LOANED` | 貸出中 | 利用者へ引き渡し済み | 不可 |
| `INSPECTION_REQUIRED` | 点検待ち | 破損等により点検・修理判断が必要 | 不可 |
| `RETIRED` | 廃止 | 利用を終了した終端状態 | 不可 |

| 現在状態 | 契機 | 次状態 | 更新主体 |
| --- | --- | --- | --- |
| `AVAILABLE` | 貸出処理成功 | `LOANED` | 本システム |
| `LOANED` | 正常返却 | `AVAILABLE` | 本システム |
| `LOANED` | 破損返却 | `INSPECTION_REQUIRED` | 本システム |
| `INSPECTION_REQUIRED` | 点検完了・再利用可 | `AVAILABLE` | 外部備品管理システム |
| `INSPECTION_REQUIRED` | 点検完了・廃止決定 | `RETIRED` | 外部備品管理システム |
| `AVAILABLE` | 廃止決定 | `RETIRED` | 外部備品管理システム |

表にない備品状態遷移は許可しない。点検・修理・廃止判断は本システムの対象外であり、外部備品管理システムが更新した状態を同期して参照する。同期データに未知の状態コードが含まれる場合は貸出不可として扱い、運用監視へ通知する。

## 5. 貸出申請

### 5.1 入力項目

| 項目 | 型・長さ | 必須 | 制約 |
| --- | --- | --- | --- |
| `equipment_id` | 英数字12文字 | 必須 | 備品マスタに存在し、廃止されていないこと |
| `start_date` | 日付 | 必須 | システム日以上、システム日から90日以内 |
| `end_date` | 日付 | 必須 | 開始日以上、開始日から30日以内 |
| `purpose` | UTF-8文字列200文字 | 必須 | 前後空白除去後1文字以上 |

開始日と終了日が同日の申請は許可する。うるう年の日付はISO 8601として妥当な場合だけ許可する。

### 5.2 予約競合判定

同一備品について、既存申請の状態が `PENDING`、`APPROVED`、`ON_LOAN` のいずれかであり、次の条件を満たす場合を重複とする。

```text
existing.start_date <= requested.end_date
AND requested.start_date <= existing.end_date
```

したがって既存申請の終了日と新規申請の開始日が同じ場合も競合する。`REJECTED`、`CANCELLED`、`RETURNED` は競合判定から除外する。
登録時は備品IDをキーに排他制御し、判定と登録を同一トランザクションで実行する。

### 5.3 登録処理

1. 入力値、認証情報、備品の存在を検証する。
2. トランザクションを開始し、対象備品の予約をロックする。
3. 予約競合判定を実行する。
4. 競合がなければ申請番号を採番し、`PENDING`、バージョン1で登録する。
5. コミット後に申請受付通知を非同期送信する。

申請番号は `REQ-YYYYMMDD-NNNNNN` 形式の19文字とする。競合時はHTTP 409を返し、申請を登録しない。

## 6. 承認・却下・取消

### 6.1 承認と却下

- 承認者は自部署の `PENDING` 申請だけを承認または却下できる。
- 更新時はリクエストの `version` とDBのバージョンを照合する。
- 却下理由は前後空白除去後1文字以上500文字以下とする。
- 成功時にバージョンを1加算し、コミット後に結果通知を非同期送信する。

### 6.2 申請取消

- 申請者は自分の `PENDING` または `APPROVED` 申請を取り消せる。
- 備品管理者は業務上必要な場合に同状態の申請を取り消せる。管理者の取消理由は必須とする。
- `ON_LOAN` 以降は取消不可とし、返却処理を使用する。
- 取消成功時は `CANCELLED` に更新し、予約枠を解放する。

## 7. 貸出処理

1. 備品管理者が申請番号と備品IDを入力する。
2. 申請が `APPROVED` で、備品IDが申請内容と一致することを確認する。
3. システム日が利用開始日以上かつ利用終了日以下であることを確認する。
4. 備品状態が `AVAILABLE` であることを確認する。
5. 同一トランザクションで申請を `ON_LOAN`、備品を `LOANED` に更新する。

利用開始日前はHTTP 409 `LOAN_PERIOD_NOT_STARTED`、利用終了日を過ぎている場合はHTTP 409 `LOAN_PERIOD_EXPIRED` を返す。備品状態が `AVAILABLE` でない場合はHTTP 409 `EQUIPMENT_NOT_AVAILABLE` を返す。いずれの場合も申請状態と備品状態を変更しない。トランザクション中の更新競合時も両方をロールバックする。

## 8. 返却処理

1. 備品管理者が申請番号、備品ID、返却状態を入力する。
2. 申請が `ON_LOAN` で、備品IDが一致することを確認する。
3. 返却状態が `NORMAL` の場合、申請を `RETURNED`、備品を `AVAILABLE` に更新する。
4. 返却状態が `DAMAGED` の場合、申請を `RETURNED`、備品を `INSPECTION_REQUIRED` に更新し、備考を必須とする。
5. コミット後に返却完了通知を非同期送信する。

同じ返却リクエストが再送された場合、同一の `Idempotency-Key` に対して初回の成功結果を返し、二重更新しない。

## 9. APIインターフェース

すべてのAPIは `/api/v1` 配下とし、JSONを送受信する。認証トークンは `Authorization: Bearer <token>` を使用する。

| HTTP method | Endpoint | 処理 | Request schema | Response schema |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/applications` | 申請登録 | `CreateApplicationRequest` | `ApplicationResponse` |
| GET | `/api/v1/applications/{application_id}` | 申請参照 | Pathのみ | `ApplicationResponse` |
| POST | `/api/v1/applications/{application_id}/approve` | 承認 | `VersionRequest` | `ApplicationResponse` |
| POST | `/api/v1/applications/{application_id}/reject` | 却下 | `RejectRequest` | `ApplicationResponse` |
| POST | `/api/v1/applications/{application_id}/cancel` | 取消 | `CancelRequest` | `ApplicationResponse` |
| POST | `/api/v1/applications/{application_id}/checkout` | 貸出 | `CheckoutRequest` | `ApplicationResponse` |
| POST | `/api/v1/applications/{application_id}/return` | 返却 | `ReturnRequest` | `ApplicationResponse` |

### 9.1 Idempotency-Key共通規則

- 表中のすべてのPOST APIで `Idempotency-Key` ヘッダーを必須とする。値はUUID形式とする。
- キーの有効範囲は認証済みユーザーIDとendpointの組み合わせとし、初回受付から24時間保持する。
- 同じ有効範囲、同じキー、同じrequest bodyの再送では業務処理を再実行せず、初回完了時と同じHTTP statusとresponse bodyを返す。
- 初回処理が完了していない間の再送にはHTTP 409 `REQUEST_IN_PROGRESS` を返し、業務データを追加更新しない。
- 同じ有効範囲とキーで異なるrequest bodyを送信した場合はHTTP 409 `IDEMPOTENCY_KEY_REUSED` を返し、業務処理を実行しない。
- 認証エラー、JSON形式不正、ヘッダー欠落はキーを保存しない。業務処理を開始した後の成功・業務エラー応答は、再送時に同じ結果を返せるよう保存する。

### 9.2 Request schema

```json
{
  "CreateApplicationRequest": {
    "equipment_id": "string(12)",
    "start_date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD",
    "purpose": "string(1..200)"
  },
  "VersionRequest": { "version": "integer >= 1" },
  "RejectRequest": { "version": "integer >= 1", "reason": "string(1..500)" },
  "CancelRequest": { "version": "integer >= 1", "reason": "string(0..500)" },
  "CheckoutRequest": { "version": "integer >= 1", "equipment_id": "string(12)" },
  "ReturnRequest": {
    "version": "integer >= 1",
    "equipment_id": "string(12)",
    "condition": "NORMAL | DAMAGED",
    "note": "string(0..500), DAMAGEDの場合は必須"
  }
}
```

申請者による取消では `reason` は任意、備品管理者による取消では1文字以上を必須とする。

### 9.3 Response schema

```json
{
  "application_id": "REQ-20260921-000001",
  "equipment_id": "PC0000000001",
  "applicant_id": "string",
  "department_id": "string",
  "start_date": "2026-09-21",
  "end_date": "2026-09-22",
  "purpose": "string",
  "status": "PENDING",
  "version": 1,
  "updated_at": "2026-09-21T10:30:00+09:00"
}
```

登録成功はHTTP 201、参照・更新成功はHTTP 200を返す。

### 9.4 Error schema

```json
{
  "error": {
    "code": "RESERVATION_CONFLICT",
    "message": "指定期間は既に予約されています。",
    "field": "start_date",
    "trace_id": "string"
  }
}
```

| HTTP status | 主なcode | 条件 |
| --- | --- | --- |
| 400 | `INVALID_JSON` | JSON形式不正 |
| 401 | `UNAUTHENTICATED` | 未認証、トークン期限切れ |
| 403 | `FORBIDDEN` | ロール、部署、所有者の権限不足 |
| 404 | `APPLICATION_NOT_FOUND`, `EQUIPMENT_NOT_FOUND` | 対象なし、または参照権限なし |
| 409 | `RESERVATION_CONFLICT`, `VERSION_CONFLICT`, `INVALID_STATUS_TRANSITION`, `EQUIPMENT_NOT_AVAILABLE`, `LOAN_PERIOD_NOT_STARTED`, `LOAN_PERIOD_EXPIRED`, `REQUEST_IN_PROGRESS`, `IDEMPOTENCY_KEY_REUSED` | 予約・更新・状態・冪等性競合 |
| 422 | `VALIDATION_ERROR` | 項目型、長さ、範囲違反 |
| 500 | `INTERNAL_ERROR` | 想定外エラー |

404では対象の存在有無を権限のない利用者へ開示しない。500の応答には内部例外やスタックトレースを含めない。

## 10. 通知API連携

業務トランザクションのコミット後、通知キュー経由で次のAPIを呼び出す。

- Method: `POST`
- Endpoint: `/notification/v1/messages`
- 接続タイムアウト: 3秒
- 読み取りタイムアウト: 5秒

Request:

```json
{
  "event_id": "UUID",
  "event_type": "APPLICATION_CREATED | APPROVED | REJECTED | CANCELLED | RETURNED",
  "recipient_user_id": "string",
  "application_id": "string(19)",
  "occurred_at": "ISO 8601 datetime with timezone"
}
```

イベントごとの通知先は次のとおりとする。対象者が複数いる場合は、受信者ごとに通知APIを1回呼び出す。同一ユーザーが複数条件に該当する場合は1件にまとめ、操作実行者本人への通知が不要なイベントでは除外する。

| event_type | recipient_user_id |
| --- | --- |
| `APPLICATION_CREATED` | 申請者の所属部署に属する有効な承認者全員 |
| `APPROVED` | 申請者 |
| `REJECTED` | 申請者 |
| `CANCELLED` | 申請者、および申請者が取り消した場合は所属部署の承認者全員 |
| `RETURNED` | 申請者、および備品管理者ロールの通知先グループ |

通知先ユーザーが0件の場合、業務処理は成功のままとし、`NO_NOTIFICATION_RECIPIENT` を運用監視へ通知する。無効化済みユーザーは通知先から除外する。

成功時はHTTP 202と `{"message_id": "string"}` を返す。400は再試行せず入力不備として監視通知し、429または5xx、タイムアウトは1分、5分、15分後に最大3回再試行する。3回失敗した場合は `event_id`、申請番号、エラーコードを運用監視へ通知する。利用目的などの本文は送信しない。

## 11. 主要な異常処理

- DB更新失敗時はトランザクションをロールバックし、申請と備品の状態をともに更新前へ戻す。
- タイムアウトで結果不明となった更新APIは、同じ `Idempotency-Key` で再実行できる。
- バージョン不一致時はHTTP 409を返し、最新データの再取得を促す。
- 通知失敗では業務データをロールバックしない。
- 予期しない例外は `trace_id` とエラー分類だけをログへ記録し、入力本文や認証トークンは記録しない。

## 12. 非機能要件

- 通常時のAPI応答時間は95パーセンタイルで2秒以内とする。
- 測定条件は同時利用者100人、1分間あたり300リクエストとする。
- 通信はTLS 1.2以上とする。
- 監査ログの保存期間は365日とし、アプリケーション利用者は削除できない。

## 13. 境界条件とテスト観点

- 開始日がシステム日、90日後、91日後の場合を確認する。
- 終了日が開始日と同日、30日後、31日後の場合を確認する。
- うるう年の2月29日と存在しない日付を確認する。
- 既存予約の開始日・終了日と一致する申請が競合することを確認する。
- `CANCELLED` または `REJECTED` の期間を再申請できることを確認する。
- 同一備品への同時申請で一方だけが登録されることを確認する。
- 権限のない部署・他人の申請を参照、更新できないことを確認する。
- 各状態について許可された遷移と禁止された遷移を確認する。
- 貸出期間外の貸出、貸出前の返却、二重返却を拒否することを確認する。
- `AVAILABLE` 以外の備品を貸し出せず、申請・備品状態が変わらないことを確認する。
- 同一 `Idempotency-Key` の同一body再送、処理中再送、異なるbody再送、24時間経過後を確認する。
- 各通知イベントで定義された利用者だけが受信者となり、重複通知されないことを確認する。
- 通知APIの400、429、5xx、タイムアウト時の再試行方針を確認する。
