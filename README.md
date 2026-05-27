# Ride Connector / 骑行晨报推送服务

Ride Connector is a daily Intervals.icu cycling briefing service. It reads today's planned
workouts and recent wellness data, creates a conservative Chinese training and weight-loss
nutrition briefing, and sends it through a WeChat Official Account template message.

Ride Connector 是一个每日骑行晨报服务。它会读取 Intervals.icu 的今日训练计划和近期生理状态，
生成保守的中文训练建议与减脂友好的营养建议，并通过微信公众号模板消息推送到微信。

## Features / 功能

- Reads today's planned workouts from Intervals.icu.
- Reads recent wellness data such as weight, sleep, resting heart rate, HRV, fatigue, and soreness when available.
- Generates conservative training advice with an OpenAI-compatible API.
- Falls back to local rule-based advice if the AI API fails.
- Sends WeChat Official Account template messages.
- Runs locally, on a server, or through GitHub Actions every day at 08:00 Asia/Shanghai.

- 读取 Intervals.icu 今日计划训练。
- 读取近期体重、睡眠、静息心率、HRV、疲劳、酸痛等可用生理状态。
- 使用 OpenAI 兼容接口生成保守训练建议。
- AI 接口失败时自动降级为本地规则建议。
- 通过微信公众号模板消息推送。
- 可在本机、服务器或 GitHub Actions 上每天北京时间 08:00 自动运行。

## Setup / 本地配置

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -e ".[dev]"
Copy-Item .env.example .env
```

Edit `.env` with your Intervals.icu API key, WeChat Official Account credentials, template ID,
recipient openid, and OpenAI-compatible API key.

请在 `.env` 中填写你的 Intervals.icu API key、微信公众号凭据、模板 ID、接收人的 openid，
以及 OpenAI 兼容接口的 API key。

Intervals.icu API key authentication uses HTTP Basic Auth with username `API_KEY` and your
personal API key as the password.

Intervals.icu API key 认证使用 HTTP Basic Auth：用户名为 `API_KEY`，密码为你的个人 API key。

## Run Once / 立即运行一次

```powershell
python -m ride_connector.jobs.daily_push --once
```

## Run Scheduler / 启动本地定时任务

```powershell
python -m ride_connector.jobs.daily_push
```

The scheduler runs every day at 08:00 in `TZ` from `.env`, defaulting to `Asia/Shanghai`.

定时任务会按 `.env` 中的 `TZ` 每天 08:00 运行，默认时区为 `Asia/Shanghai`。

## GitHub Actions / GitHub 自动运行

The repository includes `.github/workflows/daily-push.yml`. It runs every day at `00:00 UTC`,
which is `08:00 Asia/Shanghai`, and can also be triggered manually from the Actions tab.

项目已包含 `.github/workflows/daily-push.yml`。它每天 `00:00 UTC` 运行，也就是北京时间
`08:00`。你也可以在 GitHub 的 Actions 页面手动触发。

Add these repository secrets in GitHub:

请在 GitHub 仓库中添加以下 Secrets：

- `INTERVALS_API_KEY`
- `INTERVALS_ATHLETE_ID`，optional / 可选，defaults to / 默认 `0`
- `WECHAT_APP_ID`
- `WECHAT_APP_SECRET`
- `WECHAT_TEMPLATE_ID`
- `WECHAT_OPENID`
- `WECHAT_TEMPLATE_FIELD_MAP`
- `OPENAI_BASE_URL`，optional / 可选，defaults to / 默认 `https://api.openai.com/v1`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`，optional / 可选，defaults to / 默认 `gpt-4.1-mini`

Do not commit real keys to the repository.

不要把真实密钥提交到仓库。

## WeChat Template Fields / 微信模板字段

Default mapping:

默认字段映射：

```json
{
  "first": "first",
  "date": "keyword1",
  "training": "keyword2",
  "status": "keyword3",
  "advice": "keyword4",
  "nutrition": "remark"
}
```

If your template uses different field names, change `WECHAT_TEMPLATE_FIELD_MAP` in `.env` or in
GitHub Secrets.

如果你的公众号模板字段名不同，请在 `.env` 或 GitHub Secrets 中修改
`WECHAT_TEMPLATE_FIELD_MAP`。

## Tests / 测试

```powershell
pytest
```
