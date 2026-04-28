# 泡泡画图插件 使用文档

## 📖 概述

泡泡画图是一个基于 NovelAI 官方 API 的 AI 绘图插件，支持文生图、图生图、氛围转移、角色保持等多种功能。

### 🆓 Opus 免费模式

本插件支持 **Opus 免费模式**（小图模式），开启后会自动调整参数以符合 NovelAI Opus 订阅的免费生成条件：
- 分辨率限制在 **1024×1024 像素**以内
- 步数限制在 **28 步**以内

> 💡 Opus 订阅用户在此条件下可以**无限免费生成**图片，无需消耗 Anlas！
> 
> ⚠️ 注意：部分高级功能（如高分辨率、高步数）在免费模式下会被自动调整。

---

## 🎨 画图命令

### 基础命令 `nai`

直接使用提示词绘图（所有参数必须使用 `key=value` 格式）：

```
nai
tag=1girl, coffee shop, smile
```

#### 使用预设

```
nai
s1=预设名
```

#### 使用自定义参数

换行定义多个参数：

```
nai
tag=1girl, coffee shop
model=nai-diffusion-4-5-curated
画面尺寸=竖图
```

#### 使用提示词包装器

可以使用前置/后置提示词来包装主提示词：

```
nai
前置正向=best quality, masterpiece
tag=1girl, coffee shop
后置正向=solo, simple background
前置负面=lowres, bad anatomy
后置负面=extra limbs
```

最终生成的提示词：
- 正向：`best quality, masterpiece, 1girl, coffee shop, solo, simple background`
- 负面：`lowres, bad anatomy, extra limbs`

---

### AI 画图命令 `nai画图`

使用 AI 自动解析描述生成参数：

```
nai画图
s1=预设名
ds=画一个在咖啡店微笑的女孩
```

- `s1`、`s2` 等：按优先级使用多个预设
- `ds`：自然语言描述，AI 会自动转换为绘图参数

#### 使用 `nai` 参数进行个性化设置（推荐）

`nai画图` 除了支持自然语言 `ds` 让 AI 自动生成参数，也支持直接写 **与 `nai` 同款的 `key=value` 参数**来个性化控制；这些显式参数会优先生效/覆盖 AI 自动生成的结果。

示例：
```
nai画图
ds=把图里的角色改成冬装
model=nai-diffusion-4-5-curated
steps=28
size=竖图
前置正向=best quality, masterpiece
```

#### 识图（可选）

`nai画图` 和 `nai自动画图` 支持“把你发送的图片作为参考”交给**高级参数模型**进行识图（多模态）。

- 使用方式：发送命令时带上图片即可（同一条消息内）。

当你在同一条消息里发送多张图片时：

- 若启用了 `i2i` / `vibe_transfer` / `character_keep` 等参数，会按图片顺序先“消耗”对应数量。
- **剩余图片会作为识图参考**传给高级参数模型（需要开启 `llm.enable_vision=true`）。
- 可选：用 `llm.vision_image_limit` 限制传给模型的参考图片数量（0 表示不限制）。

---

### 自动画图

监听主 AI 回复，自动生成配图。

#### 查看状态
```
nai自动画图
```

#### 开启自动画图
```
nai自动画图开
s1=预设名
```

#### 关闭自动画图
```
nai自动画图关
```

> ⚠️ 自动画图的额度由开启者承担

#### 在自动画图里使用 `nai` 参数个性化

`nai自动画图` 的预设内容支持写入与 `nai` 相同的 `key=value` 参数（例如 `model/size/steps/seed/role/i2i/vibe_transfer/character_keep/前置正向...`），用于个性化控制自动出图风格与参数。

---

## 📝 预设管理

### 查看预设列表
```
nai预设列表
```

### 查看预设内容
```
nai预设查看 预设名
```

### 添加预设（管理员）
```
nai预设添加 预设名
这里是预设内容
tag=1girl, cute
negative=bad quality
size=竖图
```

### 删除预设（管理员）
```
nai预设删除 预设名
```

---

## 💰 额度系统

### 每日签到
```
/nai签到
```

### 查询额度
```
/查询额度
```

---

## 📊 队列系统

当多个用户同时请求画图时，系统会自动进行排队管理。

### 查询队列状态
```
nai队列
```

显示当前正在处理的请求数、排队等待的请求数，以及队列是否已满。

> 💡 当队列已满时，新的画图请求会被暂时拒绝，请稍后重试。

---

## 🔧 管理员命令

### 黑名单管理
```
nai黑名单添加 用户ID
nai黑名单移除 用户ID
nai黑名单列表
```

### 白名单管理
```
nai白名单添加 用户ID
nai白名单移除 用户ID
nai白名单列表
```

### 额度管理
```
nai查询用户 用户ID
nai设置额度 用户ID 次数
nai增加额度 用户ID 次数
```

---

## 🖼️ 图片引用功能

发送指令时附带的图片会按顺序加入引用列表。

### 图生图(i2i)
```
nai 1girl
i2i=true

[图片]
```

### 氛围转移(vibe_transfer)
```
nai 1girl
vibe_transfer=true
vibe_transfer_info_extract=0.8

[图片]
```

### 角色保持(character_keep)
```
nai 1girl
character_keep=true

[图片]
```

---

## ⚙️ 支持的自定义参数

| 参数 | 别名 | 说明 |
|------|------|------|
| `tag` | 正向提示词 | 期望生成的图片内容 |
| `negative` `ne` | 反向提示词 | 不想出现的内容 |
| `prepend_tag` `a_tag` | 前置正向/前置正向提示词 | 添加到正向提示词最前方 |
| `append_tag` `b_tag` | 后置正向/后置正向提示词 | 添加到正向提示词最后方 |
| `prepend_negative` `a_ne` | 前置负面/前置负面提示词 | 添加到负面提示词最前方 |
| `append_negative` `b_ne` | 后置负面/后置负面提示词 | 添加到负面提示词最后方 |
| `model` | 模型 | 选择绘图模型 |
| `artist` | 画师/画师串 | 指定画师风格 |
| `size` | 画面尺寸 | 竖图`portrait`/横图`landscape`/方图`square` 或 WxH(白名单专用) |
| `seed` | 种子 | 固定随机种子 |
| `steps` | 采样步数 | 1-50，默认23 (28以上为白名单专用)|
| `scale` | 提示词引导值 | 默认5 |
| `cfg` | 缩放引导值 | 默认0 |
| `sampler` | 采样器 | 选择采样方法 |
| `noise_schedule` `n_s` | 噪声调度 | karras等 |
| `other` | 高级配置 | SMEA等设置 |
| `i2i` | 图生图 | 引用图片进行重绘 |
| `i2i_force` `i_f` | 重绘力度 | 0-1，默认0.6 |
| `vibe_transfer` `v_t` | 氛围转移 | 参考图片风格 |
| `vibe_transfer_info_extract` `v_t_i_e` | 氛围转移信息提取度 | 0-1 |
| `vibe_transfer_ref_strength` `v_t_r_s` | 氛围转移参考强度 | 0-1 |
| `role` | 角色/多角色 | 多角色控制 |
| `character_keep` `c_k` | 角色保持/ck | 保持角色特征 |
| `character_keep_vibe` `c_k_v` | 角色保持氛围 | true/false |
| `character_keep_strength` `c_k_s` | 角色保持强度 | 0-1 |

---

## 📋 可用模型

- `nai-diffusion-3` `nai3` - NAI3 标准模型
- `nai-diffusion-furry-3` `nai3_furry` - NAI3 Furry模型
- `nai-diffusion-4-full` `nai4_full` - NAI4 完整版
- `nai-diffusion-4-curated-preview` `nai4_c_p` - NAI4 精选预览版
- `nai-diffusion-4-5-curated` `nai4.5_c` - NAI4.5 精选版
- `nai-diffusion-4-5-full` `nai4.5_full` - NAI4.5 完整版

---

## 🎯 多角色控制(role)

格式：`role=位置|正向提示词|反向提示词`

位置网格（5x5）：
```
     A    B    C    D    E
  ┌────┬────┬────┬────┬────┐
1 │ A1 │ B1 │ C1 │ D1 │ E1 │
  ├────┼────┼────┼────┼────┤
2 │ A2 │ B2 │ C2 │ D2 │ E2 │
  ├────┼────┼────┼────┼────┤
3 │ A3 │ B3 │ C3 │ D3 │ E3 │
  ├────┼────┼────┼────┼────┤
4 │ A4 │ B4 │ C4 │ D4 │ E4 │
  ├────┼────┼────┼────┼────┤
5 │ A5 │ B5 │ C5 │ D5 │ E5 │
  └────┴────┴────┴────┴────┘
```

示例：
```
nai 2girls
role=A2|1girl, cute, smile
role=D2|1girl, cool|bad anatomy
```
