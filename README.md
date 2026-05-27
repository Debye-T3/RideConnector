# Ride Connector / 骑行晨报推送服务

Ride Connector is a daily Intervals.icu cycling briefing service. It reads today's planned
workouts and recent wellness data, creates a conservative Chinese training and weight-loss
nutrition briefing, and sends it by email by default. The WeChat Official Account notifier is
still kept in the codebase and can be enabled later.

Ride Connector 是一个每日骑行晨报服务。它会读取 Intervals.icu 的今日训练计划和近期生理状态，
生成保守的中文训练建议与减脂友好的营养建议。默认推送方式已改为邮件；微信公众号推送代码仍然保留，
后续可以通过配置重新启用。

## Features / 功能

- Reads today's planned workouts from Intervals.icu.
- Reads recent wellness data such as weight, sleep, resting heart rate, HRV, fatigue, and soreness when available.
- Generates conservative training advice with an OpenAI-compatible API.
- Falls back to local rule-based advice if the AI API fails.
- Sends a Chinese plain text + HTML email by default.
- Keeps the WeChat Official Account template message integration as an optional notifier.
- Runs locally, on a server, or through GitHub Actions every day at 08:00 Asia/Shanghai.

- 读取 Intervals.icu 今日计划训练。
- 读取近期体重、睡眠、静息心率、HRV、疲劳、酸痛等可用生理状态。
- 使用 OpenAI 兼容接口生成保守训练建议。
- AI 接口失败时自动降级为本地规则建议。
- 默认发送中文纯文本 + HTML 邮件。
- 保留微信公众号模板消息推送作为可选通道。
- 可在本机、服务器或 GitHub Actions 上每天北京时间 08:00 自动运行。

## Setup / 本地配置

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -e ".[dev]"
Copy-Item .env.example .env
```

Edit `.env` with your Intervals.icu API key, SMTP credentials, recipient email address, and
OpenAI-compatible API key.

请在 `.env` 中填写你的 Intervals.icu API key、SMTP 邮箱凭据、收件邮箱，以及 OpenAI 兼容接口的
API key。

Intervals.icu API key authentication uses HTTP Basic Auth with username `API_KEY` and your
personal API key as the password.

Intervals.icu API key 认证使用 HTTP Basic Auth：用户名为 `API_KEY`，密码为你的个人 API key。

## Email Settings / 邮件配置

Default notifier:

默认推送通道：

```env
NOTIFIER=email
```

Required email variables:

必需邮件变量：

```env
EMAIL_SMTP_HOST=smtp.example.com
EMAIL_SMTP_PORT=587
EMAIL_SMTP_USER=your-email-account
EMAIL_SMTP_PASSWORD=your-smtp-app-password
EMAIL_FROM=your-email@example.com
EMAIL_TO=recipient@example.com
EMAIL_USE_TLS=true
EMAIL_USE_SSL=false
```

Use an SMTP authorization code or app password when your email provider requires it. Do not use
your normal login password unless the provider explicitly allows it.

如果邮箱服务商要求 SMTP 授权码或应用专用密码，请使用授权码，不要使用普通登录密码。

Common examples:

常见示例：

- QQ Mail: host `smtp.qq.com`, port `465`, `EMAIL_USE_SSL=true`, `EMAIL_USE_TLS=false`
- 163 Mail: host `smtp.163.com`, port `465`, `EMAIL_USE_SSL=true`, `EMAIL_USE_TLS=false`
- Gmail: host `smtp.gmail.com`, port `587`, `EMAIL_USE_TLS=true`, app password required
- Outlook: host `smtp.office365.com`, port `587`, `EMAIL_USE_TLS=true`

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
- `EMAIL_SMTP_HOST`
- `EMAIL_SMTP_PORT`
- `EMAIL_SMTP_USER`
- `EMAIL_SMTP_PASSWORD`
- `EMAIL_FROM`
- `EMAIL_TO`
- `OPENAI_API_KEY`

Optional secrets:

可选 Secrets：

- `INTERVALS_ATHLETE_ID`，defaults to / 默认 `0`
- `EMAIL_USE_TLS`，defaults to / 默认 `true`
- `EMAIL_USE_SSL`，defaults to / 默认 `false`
- `OPENAI_BASE_URL`，defaults to / 默认 `https://api.openai.com/v1`
- `OPENAI_MODEL`，defaults to / 默认 `gpt-4.1-mini`

Do not commit real keys to the repository.

不要把真实密钥提交到仓库。

## Optional WeChat Notifier / 可选微信推送

WeChat code is still available. To use it, set:

微信推送代码仍然保留。如需启用，设置：

```env
NOTIFIER=wechat
```

Then configure:

然后配置：

- `WECHAT_APP_ID`
- `WECHAT_APP_SECRET`
- `WECHAT_TEMPLATE_ID`
- `WECHAT_OPENID`
- `WECHAT_TEMPLATE_FIELD_MAP`

Default WeChat template field mapping:

默认微信模板字段映射：

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

## Tests / 测试

```powershell
pytest
```
