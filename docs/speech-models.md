# 语音合成与复刻音色

默认语音模型改为 `cosyvoice-v3-flash`。语音合成和新音色复刻共用 `TTS_MODEL` 配置，文字聊天模型不受影响。

```dotenv
TTS_MODEL=cosyvoice-v3-flash
ENABLE_TTS=true
```

API 密钥、WebSocket 地址、声音复刻地址仍使用原有 `API_KEY`、`WSS_URL` 和 `VOICE_URL`，这些配置必须属于匹配的服务地域/业务空间，不能提交真实密钥到 Git。

## 兼容规则

- 系统音色（如 longanyang）使用配置的默认模型，仍需保证该音色受此模型支持。
- 复刻音色在创建时绑定目标模型。运行时从官方音色 ID 的模型前缀选择合成模型，旧 ID 不会被盲目发送到新模型。
- 更换复刻模型时必须用原始音频重新创建音色，不能仅修改 ID 字符串或合成请求中的 model。
- 不同模型的额度和计费以百炼控制台为准。切换模型不保证永久免费，也不会自动关闭“仅使用免费额度”或开通付费。

## 迁移已有音色

先备份数据库。在 backend 目录运行：

```powershell
# 只预览，不创建音色
..\.venv\Scripts\python.exe manage.py migrate_voice_model --target-model cosyvoice-v3-flash

# 只迁移指定的本地 Voice 记录
..\.venv\Scripts\python.exe manage.py migrate_voice_model --target-model cosyvoice-v3-flash --voice-id 3 --apply

# 迁移现有 CosyVoice 复刻音色
..\.venv\Scripts\python.exe manage.py migrate_voice_model --target-model cosyvoice-v3-flash --apply
```

迁移会向原服务查询原始音频地址，为目标模型创建音色，实际合成短句验证成功后才替换本地 Voice.voice_id。Voice 主键不变，所以已有角色不必重新选音色。原始音频不可用、复刻失败或未返回音频时保留旧 ID。

原远端音色不会删除。若创建成功但验证失败，会保留新远端音色，需稍后在服务端核查处理，避免盲目重复执行产生多余音色和费用。命令不会输出密钥或带签名的音频地址。

## 故障定位

`AllocationQuota.FreeTierOnly` 表示仅免费模式下没有可用免费额度，可能已用尽或已到期，不能仅凭此错误区分两者。网页会提示检查百炼额度设置，文字回复继续；Trace 中保存语音错误码及所用模型。

语音复刻与合成的模型必须一致，参考[声音复刻文档](https://help.aliyun.com/zh/model-studio/voice-cloning-user-guide)。
