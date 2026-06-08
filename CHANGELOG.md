# CHANGELOG

## v1.6.0

Breaking Changes & New Features:
- 新增画师预设系统：配置 `artist_presets` 模板列表，通过 `/nai art` 命令切换画师风格，prompt/negative 自动注入所有生图路径
- 新增代理地址配置：`request.proxy` 支持 HTTP/SOCKS5 代理连接 NovelAI API
- 新增发送失败提示：图片生成成功但发送失败时，随机抽取三条俏皮文案提醒用户
- LLM 工具重写：`nai_generate_image` 改用 `@filter.llm_tool` 装饰器注册，参数简化为 `request: str`，与参考插件一致
- 全平台发图兼容：移除 QQ 专属 `Nodes`/`Node` 合并转发，统一使用直接图片发送，适配 Discord 等平台
- 强制抹除 Metadata：发送前始终转 JPEG 清除 prompt 等元数据，不再提供关闭开关
- 参数格式兼容：所有参数同时支持 `key=value` 和 `key value` 两种写法
- 自然语言输入：`nai画图` 及预设支持裸文本描述，无需 `ds=` 前缀
- `/nai` 命令容错：非参数裸文本自动识别为 tag，`/nai art` 不再触发 `/nai` 参数解析报错
- 等待文案更新：生成中提示改为三条爱丽数码风格文案随机

Internal:
- 代码精简：删除旧 `STNaiGenerateImageTool` dataclass 工具类 (~120行)，改用装饰器模式
- 修复 `parse_req` 末行无分隔符报错
- 修复部分重复调用和导入冗余
- 适配 Discord 平台发图

## v1.5.7

Enhancements:
- 新增支持nai画图和自动画图上传图片功能
- 我不怎么看github，所以感兴趣的可以加加反馈或聊天画画QQ群：945824082 
- 面板新增默认预设，现在是若没有正向提示词，先读取是否预存了预设，若没有，则读取默认正向，负向同理，若有提示词则覆盖。
- 为了方便编写，我将预设1,预设2,预设3...改成s1,s2,s3...;描述改为ds
- 新增批量生成功能
- 批量生成功能扩展到 nai画图 与 自动画图（预设里可写 n=）
- 批量生图时每张图都会重新走 LLM 生成参数（nai画图/自动画图）
- 在配置项添加了一个新的开关，是否将结果合并为聊天记录
- 新增角色保持（cs）存档与引用，可用于 nai、nai画图、nai自动画图
- 新增角色保持指令：cs dcs scs ccs，并支持参数 cs=名称
- 新增n额度上限限制，csaa扣除额度
- 修改了提示词以提高成功率
- 将s映射为s1，cs映射为cs1，并可使用多个cs组合

## 紧急更新
- 解决了所有人都能使用管理员指令的bug