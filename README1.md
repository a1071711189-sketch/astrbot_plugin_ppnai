# 泡泡画图 — 使用说明

NovelAI 官方 API 绘图插件，支持文生图/图生图、氛围转移、角色保持、LLM 辅助生图、自动画图、队列与额度管理。

---

## 快速上手

### 基础绘图

```
nai tag 1girl, white hair, blue eyes, beach
nai tag=1girl, beach  （= 或空格均可）
```

单行参数支持换行组合：

```
nai
tag 1girl, beach
size portrait
steps 28
```

### 批量生成

```
nai tag 1girl n 3
nai画图 ds 白发少女 n 2
```

每张图都会重新走 LLM 生成参数（`nai画图`/自动画图），扣除对应额度。

### AI 辅助画图（自然语言 → 标签）

```
nai画图 ds 画一个在海边玩耍的白发少女
nai画图 画一只在画画的猫     （裸文本直接当描述，ds= 可省略）
```

---

## 三画图模式对比

| 指令 | 说明 | 触发方式 |
|:---|:---|:---|
| `nai` | 直接使用标签绘图 | 用户主动调用 |
| `nai画图` | LLM 将自然语言转为标签后绘图 | 用户主动调用 |
| 自然对话 | 主 AI 自动判断并调用绘图工具 | 聊天中提及画图即可 |

自然对话示例：

```
User: "数码，看看你能不能调用一下绘图，画一下你在画画的图"
Bot:  "好有趣的主意～！人家画自己在画自己的自己，简直是超级套娃自画像啦～！💕🔥"
     （自动生成并发送图片）
```

### 自动画图

```
nai自动画图开
nai自动画图开 s1 猫娘
nai自动画图关
nai自动画图        → 查看当前状态
```

开启后，主 AI 的每次回复都会被自动分析并生成配图。消耗开启者的额度。

---

## 高级功能

### 图生图 (i2i)

引用图片进行重绘：

```
nai tag 1girl, school uniform
i2i true
[附带一张图片]
```

### 氛围转移 (Vibe Transfer)

参考图片的风格/构图：

```
nai tag 1girl
vibe_transfer true
[附带一张图片]
```

支持引用多张图片（受 `权限设置 → 氛围转移图片数量上限` 限制）。

### 角色保持 (Character Keep)

保持角色特征一致性，需要先通过 `/cs` 创建角色存档。

**创建角色保持：**

```
cs 角色名
[附带角色图片]
```

**角色保持指令：**

| 指令 | 说明 |
|:---|:---|
| `cs` | 创建角色保持或查看名称列表 |
| `dcs 名称` | 删除角色保持 |
| `scs 名称` | 查询外貌提示词 |
| `ccs 名称` | 修改外貌提示词 |

**生图时引用角色保持：**

```
nai tag sitting, smile
cs 角色名

# 支持多个角色保持组合
nai tag 2girls
cs1 角色A
cs2 角色B
```

### 多角色控制 (Role)

在一张图中指定不同区域角色的外貌：

```
nai tag 2girls
role A2|1girl, pink hair|bad quality
role D2|1girl, blue hair|bad quality
```

位置网格（5x5）：A-E 横向（左→右），1-5 纵向（上→下），C3 为正中间。

---

## 画师预设

### 配置

管理员在面板 `画师预设` 中添加预设条目：
- **预设名称**：如"吉卜力风"
- **画师 Prompt**：如 `studio ghibli, hayao miyazaki`
- **附加负面提示词**：如 `3d, cgi, realistic`
- **风格说明**：简短的画风描述

### 使用

```
/nai art      → 列出所有预设，标注当前选中
/nai art 3    → 切换到第 3 号预设
```

选中后，所有生图（`nai` / `nai画图` / 自动画图）都会自动注入画师风格：Prompt 前置到正向提示词，负面词追加到反向提示词。

---

## 预设管理

预设保存常用的 Prompt 组合，可在画图时快速引用：

```
nai预设添加 猫娘
tag 1girl, cat ears, tail
negative lowres, bad anatomy

nai预设列表
nai预设查看 猫娘
nai预设删除 猫娘
```

### 预设引用

```
nai s1 猫娘                    → 直接引用预设
nai画图 s1 猫娘 ds 吃东西      → 结合自然语言描述
nai自动画图开 s1 猫娘          → 自动画图使用预设
nai s1 猫娘 s2 光影增强        → 多个预设按优先级合并
```

预设之间，tag/negative 累加，其他参数（如 steps、scale）后者覆盖前者。直接输入的参数优先级最高。

---

## 参数一览

| 参数 | 别名 | 说明 | 示例 |
|:---|:---|:---|:---|
| `tag` | 正向提示词 | 期望生成的图片内容 | `tag 1girl, white hair` |
| `negative` | `ne` | 反向提示词 | `negative bad hands` |
| `model` | 模型 | 绘图模型 | `model nai-diffusion-4-5-full` |
| `size` | 画面尺寸 | portrait/landscape/square 或 WxH | `size portrait` |
| `steps` | 采样步数 | 1-50，默认 23 | `steps 28` |
| `scale` | 提示词引导值 | 默认 5 | `scale 7` |
| `cfg` | 缩放引导值 | 默认 0 | `cfg 1` |
| `sampler` | 采样器 | k_euler_ancestral 等 | `sampler k_euler` |
| `seed` | 种子 | 固定随机种子，留空随机 | `seed 12345` |
| `artist` | 画师/画师串 | 指定画师风格 | `artist hayao miyazaki` |
| `n` | 批量生成 | 批量出图张数 | `n 3` |
| `i2i` | 图生图 | true/false | `i2i true` |
| `i2i_force` | `i_f` | 重绘力度 0-1，默认 0.6 | `i2i_force 0.8` |
| `vibe_transfer` | `v_t` | 氛围转移 | `vibe_transfer true` |
| `v_t_i_e` | | 氛围转移信息提取度 0-1 | `v_t_i_e 0.8` |
| `v_t_r_s` | | 氛围转移参考强度 0-1 | `v_t_r_s 0.5` |
| `role` | 角色/多角色 | 多角色控制 | `role A2\|1girl, pink hair` |
| `character_keep` | `c_k` / `ck` | 角色保持 | `character_keep true` |
| `c_k_v` | | 角色保持氛围 true/false | `c_k_v true` |
| `c_k_s` | | 角色保持强度 0-1 | `c_k_s 0.7` |
| `noise_schedule` | `n_s` | 噪声调度 | `noise_schedule karras` |
| `other` | 高级配置 | SMEA 等 | `other 3` |
| `prepend_tag` | `a_tag` | 前置正向提示词 | `prepend_tag best quality` |
| `append_tag` | `b_tag` | 后置正向提示词 | `append_tag highres` |
| `prepend_negative` | `a_ne` | 前置负面提示词 | `prepend_negative nsfw` |
| `append_negative` | `b_ne` | 后置负面提示词 | `append_negative sticker` |

---

## 额度与签到

```
nai签到          → 每日签到获取画图额度
查询额度          → 查询剩余画图次数
nai队列          → 查看当前绘图队列
```

---

## 管理员指令

### 黑白名单

```
nai黑名单添加 123456
nai黑名单移除 123456
nai黑名单列表

nai白名单添加 123456
nai白名单移除 123456
nai白名单列表
```

白名单用户无限额度，可使用自定义尺寸和更高步数。

### 额度管理

```
nai查询用户 123456       → 查询用户额度与黑白名单状态
nai设置额度 123456 100   → 设置用户额度
nai增加额度 123456 10    → 增加用户额度
```

---

## 配置要点

| 配置项 | 说明 |
|:---|:---|
| `request.tokens` | NovelAI 官方 Persistent API Token（`pst-` 开头），支持多个轮询 |
| `request.proxy` | 代理地址，如 `http://127.0.0.1:7890`，留空不使用 |
| `request.opus_free_mode` | Opus 免费模式，强制 ≤1024x1024 + 步数≤28 |
| `llm.advanced_arg_generation_provider` | 用于将自然语言转为绘图参数的 LLM |
| `llm.enable_vision` | 启用视觉输入（需模型支持 Vision） |
| `quota.enable_quota` | 启用额度/签到系统 |
| `defaults.default_preset` | 用户未指定 s1= 时自动应用的默认预设 |
| `artist_presets` | 画师预设列表，通过 `/nai art` 切换 |
