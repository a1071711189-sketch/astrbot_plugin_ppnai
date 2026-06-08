import asyncio
import os
import sys
import types
from asyncio import Semaphore
from importlib import import_module
from importlib import util as importlib_util
from io import BytesIO
from pathlib import Path

from typing_extensions import override

from astrbot.api import logger
from astrbot.api import AstrBotConfig
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.provider import LLMResponse
from astrbot.api.message_components import Image, Reply
from astrbot.api.star import Context, Star, StarTools


def _load_src_module(module_basename: str):
    """Load a module from this plugin's src/ folder.

    1) Try normal relative import: `.<plugin>.src.<module>`.
    2) If that fails (common when loader doesn't treat src as a package),
       load from file path: `<plugin_dir>/src/<module>.py`.
    """

    pkg = __package__
    if pkg:
        try:
            return import_module(f"{pkg}.src.{module_basename}")
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                f"[nai] Relative import failed for {pkg}.src.{module_basename}; trying file-path import",
                exc_info=exc,
            )

    src_dir = Path(__file__).parent / "src"
    file_path = src_dir / f"{module_basename}.py"
    if not file_path.exists():
        raise ModuleNotFoundError(
            f"Missing src module file: {file_path} (module={module_basename})",
        )

    # Ensure parent package `<pkg>.src` exists so relative imports inside src modules work.
    src_pkg_name = f"{pkg}.src" if pkg else "src"
    if src_pkg_name not in sys.modules:
        src_pkg = types.ModuleType(src_pkg_name)
        src_pkg.__path__ = [str(src_dir)]
        sys.modules[src_pkg_name] = src_pkg

    mod_name = f"{src_pkg_name}.{module_basename}"
    spec = importlib_util.spec_from_file_location(mod_name, file_path)
    if spec is None or spec.loader is None:
        raise ModuleNotFoundError(f"Failed to create import spec for {file_path}")
    module = importlib_util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module

from .src.config import Config
from .src.data_source import GenerateError, create_client_from_config, wrapped_generate
from .src.llm import (
    ReturnToLLMError,
    llm_generate_advanced_req,
)
from .src.llm_utils import format_readable_error
from .src.models import Req
from .src.character_keep_store import CharacterKeepStore, extract_nai_tag
from .src.params import parse_req
from .src.artist_preset import (
    SessionContext,
    SessionRuntimeState,
    SessionStateStore,
    inject_artist_negative,
    inject_artist_prompt,
    parse_artist_presets,
    resolve_artist_preset,
)
from .src.image_io import astrip_image_metadata
from .src.user_manager import UserManager
from .src.preset_manager import PresetManager
from .src.queue_manager import get_shared_queue
from .src.handlers_nai import handle_cmd_nai, handle_nai_draw
try:
    from .src.handlers_admin import (
        handle_add_blacklist,
        handle_add_quota,
        handle_add_whitelist,
        handle_admin_query_user,
        handle_checkin,
        handle_list_blacklist,
        handle_list_whitelist,
        handle_query_quota,
        handle_queue_status,
        handle_remove_blacklist,
        handle_remove_whitelist,
        handle_set_quota,
    )
except Exception:  # noqa: BLE001
    try:
        _m = _load_src_module("handlers_admin")
        handle_add_blacklist = _m.handle_add_blacklist
        handle_add_quota = _m.handle_add_quota
        handle_add_whitelist = _m.handle_add_whitelist
        handle_admin_query_user = _m.handle_admin_query_user
        handle_checkin = _m.handle_checkin
        handle_list_blacklist = _m.handle_list_blacklist
        handle_list_whitelist = _m.handle_list_whitelist
        handle_query_quota = _m.handle_query_quota
        handle_queue_status = _m.handle_queue_status
        handle_remove_blacklist = _m.handle_remove_blacklist
        handle_remove_whitelist = _m.handle_remove_whitelist
        handle_set_quota = _m.handle_set_quota
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to import admin handlers module (.src.handlers_admin). "
            "Admin/quota commands will be unavailable. "
            "This is usually caused by incomplete plugin deployment (missing 'src/handlers_admin.py' or package files).",
        )

        def _make_missing_admin_handler(handler_name: str):
            async def _handler(_plugin, event):
                yield event.plain_result(
                    "管理员/额度模块加载失败，相关命令暂不可用。\n"
                    "请确认已完整部署插件文件（尤其是 src/handlers_admin.py 与 src/__init__.py），然后重启 AstrBot。\n"
                    f"缺失处理器：{handler_name}",
                )

            return _handler

        handle_checkin = _make_missing_admin_handler("handle_checkin")
        handle_queue_status = _make_missing_admin_handler("handle_queue_status")
        handle_query_quota = _make_missing_admin_handler("handle_query_quota")
        handle_add_blacklist = _make_missing_admin_handler("handle_add_blacklist")
        handle_remove_blacklist = _make_missing_admin_handler("handle_remove_blacklist")
        handle_list_blacklist = _make_missing_admin_handler("handle_list_blacklist")
        handle_add_whitelist = _make_missing_admin_handler("handle_add_whitelist")
        handle_remove_whitelist = _make_missing_admin_handler("handle_remove_whitelist")
        handle_list_whitelist = _make_missing_admin_handler("handle_list_whitelist")
        handle_add_quota = _make_missing_admin_handler("handle_add_quota")
        handle_set_quota = _make_missing_admin_handler("handle_set_quota")
        handle_admin_query_user = _make_missing_admin_handler("handle_admin_query_user")
try:
    from .src.handlers_preset import (
        handle_preset_add,
        handle_preset_delete,
        handle_preset_list,
        handle_preset_view,
    )
except Exception:  # noqa: BLE001
    try:
        _m = _load_src_module("handlers_preset")
        handle_preset_add = _m.handle_preset_add
        handle_preset_delete = _m.handle_preset_delete
        handle_preset_list = _m.handle_preset_list
        handle_preset_view = _m.handle_preset_view
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to import preset handlers module (.src.handlers_preset). "
            "Preset commands will be unavailable. "
            "This is usually caused by incomplete plugin deployment (missing 'src/handlers_preset.py' or package files).",
        )

        def _make_missing_preset_handler(handler_name: str):
            async def _handler(_plugin, event):
                yield event.plain_result(
                    "预设模块加载失败，相关命令暂不可用。\n"
                    "请确认已完整部署插件文件（尤其是 src/handlers_preset.py 与 src/__init__.py），然后重启 AstrBot。\n"
                    f"缺失处理器：{handler_name}",
                )

            return _handler

        handle_preset_add = _make_missing_preset_handler("handle_preset_add")
        handle_preset_delete = _make_missing_preset_handler("handle_preset_delete")
        handle_preset_list = _make_missing_preset_handler("handle_preset_list")
        handle_preset_view = _make_missing_preset_handler("handle_preset_view")
try:
    from .src.handlers_cs import (
        handle_ccs,
        handle_cs,
        handle_dcs,
        handle_scs,
    )
except Exception:  # noqa: BLE001
    try:
        _m = _load_src_module("handlers_cs")
        handle_ccs = _m.handle_ccs
        handle_cs = _m.handle_cs
        handle_dcs = _m.handle_dcs
        handle_scs = _m.handle_scs
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to import cs handlers module (.src.handlers_cs). "
            "CS commands will be unavailable."
        )

        def _make_missing_cs_handler(handler_name: str):
            async def _handler(_plugin, event):
                yield event.plain_result(
                    "角色保持模块加载失败，相关命令暂不可用。\n"
                    "请确认已完整部署插件文件（尤其是 src/handlers_cs.py 与 src/__init__.py），然后重启 AstrBot。\n"
                    f"缺失处理器：{handler_name}"
                )

            return _handler

        handle_cs = _make_missing_cs_handler("handle_cs")
        handle_dcs = _make_missing_cs_handler("handle_dcs")
        handle_scs = _make_missing_cs_handler("handle_scs")
        handle_ccs = _make_missing_cs_handler("handle_ccs")
from .src.handlers_auto import (
    handle_auto_draw,
    handle_auto_draw_off,
    handle_auto_draw_on,
    handle_llm_response_auto_draw,
)
try:
    from .src.auto_draw_store import AutoDrawStoreManager
except Exception:  # noqa: BLE001
    try:
        AutoDrawStoreManager = _load_src_module("auto_draw_store").AutoDrawStoreManager
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to import auto-draw store module (.src.auto_draw_store). "
            "Auto-draw state persistence will be disabled. "
            "This is usually caused by incomplete plugin deployment (missing 'src/auto_draw_store.py' or package files).",
        )

        class AutoDrawStoreManager:  # type: ignore[no-redef]
            def __init__(self, _data_dir: Path):
                pass

            async def ato_runtime(self) -> dict[str, dict | None]:
                return {}

            async def asave_from_runtime(self, _auto_draw_info: dict[str, dict | None]) -> None:
                return None

COMMAND = "nai"
PLUGIN_NAME = "astrbot_plugin_ppnai"

# region help

# 帮助文档路径
USAGE_MD_PATH = Path(__file__).parent / "docs" / "USAGE.md"


def load_usage_md() -> str:
    """读取 USAGE.md 文件内容作为帮助信息"""
    try:
        if USAGE_MD_PATH.exists():
            return USAGE_MD_PATH.read_text(encoding="utf-8")
        else:
            logger.warning(f"帮助文档不存在: {USAGE_MD_PATH}")
            return "# 泡泡画图\n\n帮助文档暂不可用，请联系管理员。"
    except Exception as e:
        logger.exception(f"读取帮助文档失败: {e}")
        return "# 泡泡画图\n\n帮助文档加载失败，请联系管理员。"


# endregion


def _default_help_text() -> str:
    return "# 泡泡画图\n\n帮助文档加载中，请稍后重试。"


def _cleanup_legacy_help_cache() -> int:
    """清理旧版本遗留的帮助图片缓存（help_*.png）。

    旧实现会把 help markdown 渲染落盘到 data_dir/cache 下，若未清理可能无限增长。
    当前版本不再落盘，但仍在启动时做一次保底清理。
    """
    try:
        data_dir: Path = StarTools.get_data_dir(PLUGIN_NAME)
        cache_dir = data_dir / "cache"
        if not cache_dir.exists():
            return 0

        removed = 0
        for p in cache_dir.glob("help_*.png"):
            if not p.is_file():
                continue
            try:
                p.unlink()
                removed += 1
            except FileNotFoundError:
                continue
            except Exception as ex:  # noqa: BLE001
                logger.debug(f"Failed to delete legacy help cache file: {p} ({ex!r})")
        return removed
    except Exception as ex:  # noqa: BLE001
        logger.debug(f"Legacy help cache cleanup failed: {ex!r}")
        return 0


WAITING_REPLIES = [
    "了解了解～把你的想象交给我吧，我会把它变成现实的！",
    "嘿嘿～这个委托听起来很有趣！数据加载中……生成启动！",
    "指令确认！爱丽数码绘画模式全开，马上为你调配最棒的色彩！",
]


class Plugin(Star):
    """使用指令 nai 查看详细帮助"""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context, config)
        self.config = Config.model_validate(config)

        # Per-plugin HTTP client (avoid module-level global state).
        self._http_client = None
        self._http_client_sig: tuple[str, float, float] | None = None
        self._http_client_lock = asyncio.Lock()

        # Background tasks spawned by handlers (auto-draw etc.).
        # We track them so plugin shutdown can cancel/await cleanly.
        self._background_tasks: set[asyncio.Task] = set()
        
        # 初始化用户管理器和预设管理器，数据存储在插件目录下的 data 文件夹
        data_dir: Path = StarTools.get_data_dir(PLUGIN_NAME)
        self.user_manager = UserManager(data_dir)
        self.preset_manager = PresetManager(data_dir)

        cs_dir = data_dir / "cs"
        cssaying_path = Path(__file__).parent / "src" / "prompts" / "cssaying.txt"
        self.cs_store = CharacterKeepStore(cs_dir, cssaying_path)

        self._auto_draw_store = AutoDrawStoreManager(data_dir)

        self._artist_state_store = SessionStateStore()
        self._artist_presets = parse_artist_presets(
            self.config.artist_presets.presets
        )
        
        # 自动画图状态（按会话存储）
        # key: unified_msg_origin
        # value: None 表示关闭，AutoDrawState 表示开启
        #   - enabled: 是否开启
        #   - presets: 预设名列表，按优先级排序 [s1, s2, ...]
        #   - opener_user_id: 开启者的用户ID，用于扣额度
        # 延迟到 initialize 中异步加载（避免潜在的磁盘 I/O 阻塞）
        self.auto_draw_info: dict[str, dict | None] = {}

        self._usage_md_cache: str | None = None
        
        # Token 轮询索引
        self._token_index = 0
        
        # 画图队列（进程内共享，避免多实例导致并发翻倍）
        self._queue = get_shared_queue()

    @override
    async def initialize(self):
        # 在事件循环中初始化信号量（共享队列状态）
        self._queue.ensure(self.config.request.max_concurrent)

        # 清理旧版本遗留的 help 图片缓存（best-effort，避免磁盘膨胀）
        try:
            removed = await asyncio.to_thread(_cleanup_legacy_help_cache)
            if removed:
                logger.info(f"[nai] 已清理旧帮助缓存图片 {removed} 个")
        except Exception:  # noqa: BLE001
            logger.debug("[nai] Legacy help cache cleanup skipped")

        # 避免在事件循环中做同步文件 I/O
        self._usage_md_cache = await asyncio.to_thread(load_usage_md)

        # 预加载预设与自动画图状态，避免后续在指令处理期间触发同步文件 I/O
        try:
            await asyncio.to_thread(self.user_manager.reload)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to preload user data")
        try:
            await asyncio.to_thread(self.preset_manager.reload)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to preload presets")
        try:
            self.auto_draw_info = await self._auto_draw_store.ato_runtime()
        except Exception:  # noqa: BLE001
            logger.exception("Failed to load persisted auto_draw_info")
            self.auto_draw_info = {}
        logger.info(
            f"[nai] 队列系统初始化 pid={os.getpid()} instance={id(self)}: "
            f"最大并发={self.config.request.max_concurrent}, 最大队列={self.config.request.max_queue_size}"
        )

    @override
    async def terminate(self):
        # Cancel/await background tasks (best-effort).
        tasks = [t for t in self._background_tasks if not t.done()]
        for t in tasks:
            t.cancel()
        if tasks:
            try:
                await asyncio.gather(*tasks, return_exceptions=True)
            except Exception:  # noqa: BLE001
                logger.exception("Failed while awaiting background tasks")

        try:
            await self._auto_draw_store.asave_from_runtime(self.auto_draw_info)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to persist auto_draw_info")
        try:
            await self._close_http_client()
        except Exception:  # noqa: BLE001
            logger.exception("Failed to close http client")

    def _http_client_signature(self) -> tuple[str, float, float]:
        return (
            str(self.config.request.base_url),
            float(self.config.request.connect_timeout),
            float(self.config.request.read_timeout),
        )

    async def get_http_client(self):
        """Get this plugin instance's pooled AsyncClient (recreated on config change)."""
        sig = self._http_client_signature()
        async with self._http_client_lock:
            if self._http_client is not None and self._http_client_sig == sig:
                return self._http_client
            if self._http_client is not None:
                try:
                    await self._http_client.aclose()
                except Exception:  # noqa: BLE001
                    logger.debug("[nai] Failed to close previous http client", exc_info=True)

            self._http_client = create_client_from_config(self.config)
            self._http_client_sig = sig
            return self._http_client

    async def _close_http_client(self) -> None:
        async with self._http_client_lock:
            if self._http_client is None:
                return
            try:
                await self._http_client.aclose()
            finally:
                self._http_client = None
                self._http_client_sig = None

    def _create_background_task(self, coro, *, name: str | None = None) -> asyncio.Task:
        """Create and track a background task to avoid lost exceptions/leaks."""

        task = asyncio.create_task(coro, name=name)
        self._background_tasks.add(task)

        def _on_done(t: asyncio.Task):
            self._background_tasks.discard(t)
            try:
                exc = t.exception()
            except asyncio.CancelledError:
                return
            except Exception:  # noqa: BLE001
                logger.exception("Background task callback failed")
                return
            if exc is not None:
                logger.exception("Background task failed", exc_info=exc)

        task.add_done_callback(_on_done)
        return task

    async def generate_help(self, umo: str) -> str:
        """读取 USAGE.md 文件内容作为帮助信息（避免同步磁盘 I/O 阻塞事件循环）"""
        if self._usage_md_cache:
            return self._usage_md_cache
        try:
            self._usage_md_cache = await asyncio.to_thread(load_usage_md)
            return self._usage_md_cache
        except Exception:  # noqa: BLE001
            return _default_help_text()

    async def persist_auto_draw_info(self) -> None:
        """Persist auto_draw_info to disk without blocking event loop (best-effort)."""
        await self._auto_draw_store.asave_from_runtime(self.auto_draw_info)
    
    async def _render_markdown_to_images(self, markdown_content: str) -> list[bytes]:
        """使用 pillowmd 将 Markdown 渲染为 PNG bytes 列表（不落盘，避免临时文件泄漏）"""
        try:
            import pillowmd

            def _load_style():
                # 样式路径
                style_path = Path("data/styles/夏日冲浪")
                if style_path.exists():
                    return pillowmd.LoadMarkdownStyles(str(style_path))
                logger.warning(f"样式路径不存在: {style_path}，使用默认样式")
                return pillowmd.MdStyle()

            # pillowmd 样式加载可能涉及磁盘 I/O，放到线程池避免阻塞事件循环
            style = await asyncio.to_thread(_load_style)
            
            # 使用异步接口渲染
            # autoPage=True 支持长图分页
            render_result = await style.AioRender(
                text=markdown_content,
                useImageUrl=True,
                autoPage=True
            )
            
            # MdRenderResult 对象包含 images 列表
            if hasattr(render_result, 'images'):
                images = render_result.images
            elif isinstance(render_result, list):
                images = render_result
            else:
                # 回退处理
                images = [render_result]

            async def _img_to_png_bytes(img) -> bytes:
                def _do_save() -> bytes:
                    buf = BytesIO()
                    img.save(buf, format="PNG")
                    return buf.getvalue()

                return await asyncio.to_thread(_do_save)

            pages = await asyncio.gather(*[_img_to_png_bytes(img) for img in images])
            return list(pages)
            
        except ImportError:
            logger.warning("pillowmd 未安装，回退到远程渲染")
            return []
        except Exception as e:
            logger.exception(f"pillowmd 渲染失败: {e}")
            return []
    
    def _get_user_id(self, event: AstrMessageEvent) -> str:
        """从事件中获取用户ID"""
        return event.get_sender_id()
    
    def _check_permission(self, event: AstrMessageEvent) -> bool:
        """检查是否是管理员"""
        # 这里简单判断，可以根据 AstrBot 的实际权限系统调整
        is_admin = getattr(event, "is_admin", None)
        if callable(is_admin):
            try:
                return bool(is_admin())
            except Exception:
                return False
        if isinstance(is_admin, bool):
            return is_admin
        return False
    
    def _get_next_token(self) -> str:
        """轮询获取下一个可用的 Token"""
        tokens = self.config.request.tokens
        if not tokens:
            return ""
        token = tokens[self._token_index % len(tokens)]
        self._token_index = (self._token_index + 1) % len(tokens)
        return token

    async def _run_with_retry(self, func):
        """内部重试包装器（不外显）。

        func: 一个无参 async callable
        """
        retries = max(0, int(getattr(self.config.request, "retry_times", 0) or 0))
        wait_s = float(getattr(self.config.request, "retry_wait", 0.0) or 0.0)

        last_exc: Exception | None = None
        for attempt in range(retries + 1):
            try:
                return await func()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                last_exc = e
                if attempt >= retries:
                    raise
                if wait_s > 0:
                    await asyncio.sleep(wait_s)
        assert last_exc is not None
        raise last_exc
    
    def _get_queue_status(self) -> str:
        """获取当前队列状态字符串"""
        queue_total = self._queue.queue_status()
        if queue_total > 1:
            return f"（当前队列：{queue_total}）"
        return ""

    def _ensure_semaphore(self) -> Semaphore:
        """确保并发信号量已初始化（兼容极端情况下 initialize 尚未执行）"""
        sem, _ = self._queue.ensure(self.config.request.max_concurrent)
        return sem
    
    def _get_reply_text(self, event: AstrMessageEvent) -> str:
        """获取引用消息的文本内容"""
        try:
            # 检查消息链中是否有Reply组件
            for component in event.message_obj.message:
                if isinstance(component, Reply):
                    # Reply组件包含被引用消息的信息
                    # 尝试获取Reply组件的文本属性
                    if hasattr(component, 'text') and component.text:
                        return component.text
                    
                    # 如果Reply有content属性
                    if hasattr(component, 'content') and component.content:
                        return str(component.content)
                    
                    # 如果有message属性（某些实现）
                    if hasattr(component, 'message'):
                        msg = component.message
                        if isinstance(msg, str):
                            return msg
                        elif hasattr(msg, 'get_plain_text'):
                            return msg.get_plain_text()
                    
                    # 尝试从event的原始消息中获取
                    if hasattr(event.message_obj, 'reply') and event.message_obj.reply:
                        reply_msg = event.message_obj.reply
                        if hasattr(reply_msg, 'message') and isinstance(reply_msg.message, str):
                            return reply_msg.message
                        elif hasattr(reply_msg, 'text') and isinstance(reply_msg.text, str):
                            return reply_msg.text
                    
                    return ""
            
            return ""
        except Exception:
            return ""

    def _get_artist_injection(self, event: AstrMessageEvent) -> tuple[str, str]:
        """获取当前会话选中画师预设的 prompt 和 negative_prompt。"""
        session = SessionContext.from_event(event)
        state = self._artist_state_store.get(session)
        selected = resolve_artist_preset(self._artist_presets, state)
        if selected:
            return selected.prompt, selected.negative_prompt
        return "", ""

    def _apply_artist_preset(self, req, event: AstrMessageEvent) -> None:
        """将会话级画师预设注入到请求参数中。"""
        artist_prompt, artist_negative = self._get_artist_injection(event)
        if artist_prompt:
            req.tag = inject_artist_prompt(req.tag, artist_prompt)
        if artist_negative:
            req.negative = inject_artist_negative(req.negative, artist_negative)

    async def _strip_images(self, images: list[bytes]) -> list[bytes]:
        """对图片列表批量抹除 metadata。"""
        return await asyncio.gather(*[astrip_image_metadata(img) for img in images])

    async def _parse_args(
        self,
        event: AstrMessageEvent,
        is_whitelisted: bool = False,
    ) -> tuple[Req, int] | None:
        """解析命令参数，支持多预设
        
        预设格式：s1=xxx, s2=xxx, ...
        优先级：直接参数 > s1 > s2 > ...
        tag 和 negative 是累加，其他参数是覆盖
        """
        raw_params = event.message_str.removeprefix(COMMAND).strip()
        if not raw_params:
            return None
        
        # 解析所有参数行
        lines = raw_params.split('\n')
        direct_params: list[tuple[str, str]] = []  # 直接参数
        preset_params_list: list[list[tuple[str, str]]] = []  # 按预设编号排序的预设参数
        preset_numbers: list[int] = []  # 预设编号列表
        cs_entries: dict[int, str] = {}
        
        import re
        preset_pattern = re.compile(r'^s(\d+)$')
        cs_pattern = re.compile(r'^cs(\d+)$')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue

            if '=' in line:
                key, value = line.split('=', 1)
            elif ' ' in line:
                key, value = line.split(' ', 1)
            else:
                raise ValueError(f"参数格式错误：'{line}'，请使用如 tag=xxx 或 tag xxx 的格式")
            key = key.strip()
            value = value.strip()

            if key == "cs":
                cs_num = 1
            else:
                cs_match = cs_pattern.match(key)
                cs_num = int(cs_match.group(1)) if cs_match else 0

            if cs_num:
                existing = cs_entries.get(cs_num)
                if existing and existing != value:
                    raise ValueError(f"cs{cs_num} 重复且不一致")
                cs_entries[cs_num] = value
                continue

            # 检查是否是预设参数
            if key == "s":
                preset_num = 1
            else:
                match = preset_pattern.match(key)
                preset_num = int(match.group(1)) if match else 0

            if preset_num:
                preset = await asyncio.to_thread(self.preset_manager.get_preset, value)
                if preset is None:
                    raise ValueError(f"预设 {value} 不存在，使用 nai预设列表 查看可用预设")

                # 解析预设内容
                preset_lines = preset.content.split('\n')
                preset_params: list[tuple[str, str]] = []
                for pl in preset_lines:
                    pl = pl.strip()
                    if not pl:
                        continue
                    if '=' in pl:
                        pk, pv = pl.split('=', 1)
                        if pk.strip() == "cs":
                            continue
                        preset_params.append((pk.strip(), pv.strip()))
                    else:
                        # 没有 = 号的行视为 tag
                        preset_params.append(('tag', pl))

                preset_numbers.append(preset_num)
                preset_params_list.append(preset_params)
            else:
                direct_params.append((key, value))

        # 默认预设兜底：用户未指定任何 sN= 时，自动应用配置中的默认预设
        if not preset_numbers:
            default_name = (self.config.defaults.default_preset or "").strip()
            if default_name:
                default_preset = await asyncio.to_thread(
                    self.preset_manager.get_preset, default_name
                )
                if default_preset is None:
                    logger.warning(
                        f"[nai] defaults.default_preset 配置为 {default_name!r}，"
                        f"但该预设不存在，已跳过"
                    )
                else:
                    default_preset_params: list[tuple[str, str]] = []
                    for pl in default_preset.content.split('\n'):
                        pl = pl.strip()
                        if not pl:
                            continue
                        if '=' in pl:
                            pk, pv = pl.split('=', 1)
                            if pk.strip() == "cs":
                                continue
                            default_preset_params.append((pk.strip(), pv.strip()))
                        else:
                            default_preset_params.append(('tag', pl))
                    preset_numbers.append(1)
                    preset_params_list.append(default_preset_params)

        # 按预设编号排序（1, 2, 3, ...）
        sorted_presets = sorted(zip(preset_numbers, preset_params_list), key=lambda x: x[0])
        
        # 合并参数
        # - tag 和 negative 是累加的（按优先级顺序）
        # - prepend_* 是累加的（高优先级在前）
        # - append_* 是累加的（高优先级在后）
        # - 其他参数是覆盖的
        merged: dict[str, str] = {}
        tag_parts: list[str] = []
        negative_parts: list[str] = []
        prepend_tag_parts: list[str] = []
        append_tag_parts: list[str] = []
        prepend_negative_parts: list[str] = []
        append_negative_parts: list[str] = []
        
        # 从最低优先级到最高：sN, ..., s2, s1, 直接参数
        all_params_groups = [p for _, p in reversed(sorted_presets)] + [direct_params]
        
        for params in all_params_groups:
            for key, value in params:
                if key == 'tag':
                    tag_parts.append(value)
                elif key in ('negative', '反向提示词'):
                    negative_parts.append(value)
                elif key in ('prepend_tag', '前置正向', '前置正向提示词'):
                    # 高优先级在前，所以后遍历的插入到列表开头
                    prepend_tag_parts.insert(0, value)
                elif key in ('append_tag', '后置正向', '后置正向提示词'):
                    # 高优先级在后，所以后遍历的追加到列表末尾
                    append_tag_parts.append(value)
                elif key in ('prepend_negative', '前置负面', '前置负面提示词'):
                    # 高优先级在前
                    prepend_negative_parts.insert(0, value)
                elif key in ('append_negative', '后置负面', '后置负面提示词'):
                    # 高优先级在后
                    append_negative_parts.append(value)
                else:
                    # 其他参数直接覆盖
                    merged[key] = value
        
        # 解析批量数量（不参与绘图参数传递）
        raw_count = merged.pop("n", "")
        if raw_count:
            if not raw_count.isdigit() or int(raw_count) < 1:
                raise ValueError("参数 n 必须是大于等于 1 的整数")
            batch_count = int(raw_count)
        else:
            batch_count = 1

        max_n = int(getattr(self.config.request, "max_n", 0) or 0)
        if max_n > 0 and batch_count > max_n:
            raise ValueError(f"参数 n 不能超过 {max_n}")

        if cs_entries:
            user_id = self._get_user_id(event)
            for cs_num, cs_name in sorted(cs_entries.items(), key=lambda x: x[0]):
                exists = await asyncio.to_thread(self.cs_store.exists, user_id, cs_name)
                if not exists:
                    raise ValueError(f"角色保持 {cs_name} 不存在，请先使用 /cs 创建")
                cs_content = await asyncio.to_thread(self.cs_store.read, user_id, cs_name)
                cs_tag = extract_nai_tag(cs_content)
                if not cs_tag:
                    raise ValueError("未找到 NovelAI tag style 外貌提示词内容")
                tag_parts.append(cs_tag)

        # 构建最终参数字符串
        final_params: list[str] = []
        
        # 合并 tag（按优先级顺序）
        if tag_parts:
            final_params.append(f'tag={", ".join(tag_parts)}')
        
        # 合并 prepend/append 提示词
        if prepend_tag_parts:
            final_params.append(f'prepend_tag={", ".join(prepend_tag_parts)}')
        if append_tag_parts:
            final_params.append(f'append_tag={", ".join(append_tag_parts)}')
        if prepend_negative_parts:
            final_params.append(f'prepend_negative={", ".join(prepend_negative_parts)}')
        if append_negative_parts:
            final_params.append(f'append_negative={", ".join(append_negative_parts)}')
        
        # 添加其他参数
        for key, value in merged.items():
            final_params.append(f'{key}={value}')
        
        # 合并 negative
        if negative_parts:
            final_params.append(f'negative={", ".join(negative_parts)}')
        
        final_raw = '\n'.join(final_params)
        
        req = await parse_req(final_raw, event.message_obj.message, self.config, is_whitelisted)
        return req, batch_count

    # ========== 签到命令 ==========
    
    @filter.command("nai签到")
    async def cmd_checkin(self, event: AstrMessageEvent):
        """每日签到获取画图额度"""
        async for result in handle_checkin(self, event):
            yield result
    
    @filter.command("nai队列")
    async def cmd_queue_status(self, event: AstrMessageEvent):
        """查询当前队列状态"""
        async for result in handle_queue_status(self, event):
            yield result
    
    @filter.command("查询额度")
    async def cmd_query_quota(self, event: AstrMessageEvent):
        """查询自己的画图额度"""
        async for result in handle_query_quota(self, event):
            yield result

    # ========== 管理员命令 ==========
    
    @filter.command("nai黑名单添加")
    async def cmd_add_blacklist(self, event: AstrMessageEvent):
        """将用户添加到黑名单（管理员）"""
        async for result in handle_add_blacklist(self, event):
            yield result
    
    @filter.command("nai黑名单移除")
    async def cmd_remove_blacklist(self, event: AstrMessageEvent):
        """将用户从黑名单移除（管理员）"""
        async for result in handle_remove_blacklist(self, event):
            yield result
    
    @filter.command("nai黑名单列表")
    async def cmd_list_blacklist(self, event: AstrMessageEvent):
        """查看黑名单列表（管理员）"""
        async for result in handle_list_blacklist(self, event):
            yield result
    
    @filter.command("nai白名单添加")
    async def cmd_add_whitelist(self, event: AstrMessageEvent):
        """将用户添加到白名单（管理员）"""
        async for result in handle_add_whitelist(self, event):
            yield result
    
    @filter.command("nai白名单移除")
    async def cmd_remove_whitelist(self, event: AstrMessageEvent):
        """将用户从白名单移除（管理员）"""
        async for result in handle_remove_whitelist(self, event):
            yield result
    
    @filter.command("nai白名单列表")
    async def cmd_list_whitelist(self, event: AstrMessageEvent):
        """查看白名单列表（管理员）"""
        async for result in handle_list_whitelist(self, event):
            yield result
    
    @filter.command("nai查询用户")
    async def cmd_admin_query_user(self, event: AstrMessageEvent):
        """查询用户额度（管理员）"""
        async for result in handle_admin_query_user(self, event):
            yield result
    
    @filter.command("nai设置额度")
    async def cmd_set_quota(self, event: AstrMessageEvent):
        """设置用户额度（管理员）"""
        async for result in handle_set_quota(self, event):
            yield result
    
    @filter.command("nai增加额度")
    async def cmd_add_quota(self, event: AstrMessageEvent):
        """增加用户额度（管理员）"""
        async for result in handle_add_quota(self, event):
            yield result

    # ========== 预设命令 ==========
    
    @filter.command("nai预设列表")
    async def cmd_preset_list(self, event: AstrMessageEvent):
        """查看预设列表"""
        async for result in handle_preset_list(self, event):
            yield result
    
    @filter.command("nai预设查看")
    async def cmd_preset_view(self, event: AstrMessageEvent):
        """查看预设详细内容"""
        async for result in handle_preset_view(self, event):
            yield result
    
    @filter.command("nai预设添加")
    async def cmd_preset_add(self, event: AstrMessageEvent):
        """添加预设（管理员）"""
        async for result in handle_preset_add(self, event):
            yield result
    
    @filter.command("nai预设删除")
    async def cmd_preset_delete(self, event: AstrMessageEvent):
        """删除预设（管理员）"""
        async for result in handle_preset_delete(self, event):
            yield result

    # ========== 角色保持命令 ==========

    @filter.command("cs")
    async def cmd_cs(self, event: AstrMessageEvent):
        """角色保持：创建/列表"""
        async for result in handle_cs(self, event):
            yield result

    @filter.command("dcs")
    async def cmd_dcs(self, event: AstrMessageEvent):
        """角色保持删除"""
        async for result in handle_dcs(self, event):
            yield result

    @filter.command("scs")
    async def cmd_scs(self, event: AstrMessageEvent):
        """查询角色保持外貌提示词"""
        async for result in handle_scs(self, event):
            yield result

    @filter.command("ccs")
    async def cmd_ccs(self, event: AstrMessageEvent):
        """修改角色保持外貌提示词"""
        async for result in handle_ccs(self, event):
            yield result

    # ========== LLM 工具 ==========

    @filter.llm_tool(name="nai_generate_image")
    async def nai_generate_image_tool(self, event: AstrMessageEvent, request: str) -> str:
        """根据用户描述生成一张 NovelAI 图片并直接发送到当前会话。

        Args:
            request(string): 用户想绘制的画面描述，可以是中文自然语言或英文标签。
        """
        user_id = self._get_user_id(event)
        if self.user_manager.is_blacklisted(user_id):
            return "用户已被加入黑名单，无法使用画图功能"

        is_whitelisted = self.user_manager.is_whitelisted(user_id)
        quota_enabled = self.config.quota.enable_quota
        if quota_enabled and not is_whitelisted:
            can_use, reason = self.user_manager.can_use(user_id)
            if not can_use:
                return reason

        try:
            req = await llm_generate_advanced_req(
                instructions=f"画一张图\n{request.strip()}",
                config=self.config,
                ctx=self.context,
                event=event,
            )
        except ReturnToLLMError as e:
            return f"图片生成失败：{e}"
        except Exception as e:
            logger.exception("LLM tool: advanced req generation failed")
            return f"图片生成失败：{format_readable_error(e)}"

        self._apply_artist_preset(req, event)

        if quota_enabled and not is_whitelisted:
            quota = self.user_manager.get_quota(user_id)
            if quota < 1:
                return "你的画图次数已用完，请/nai签到获取额度"
            self.user_manager.consume_quota_n(user_id, 1)

        token = self._get_next_token()
        try:
            image = await wrapped_generate(req, self.config, token=token, client_getter=self.get_http_client)
        except Exception as e:
            logger.exception("LLM tool: image generation failed")
            return f"图片生成失败：{format_readable_error(e)}"

        image = await astrip_image_metadata(image)

        try:
            chain = MessageChain([Image.fromBytes(image)])
            await self.context.send_message(event.unified_msg_origin, chain)
        except Exception:
            logger.exception("LLM tool: send image failed")
            import random as _r
            from .src.handlers_shared import SEND_FAILURE_REPLIES as _sfr
            return _r.choice(_sfr)

        return "图片已发送。"

    # ========== 画师预设命令 ==========

    @filter.command("nai art")
    async def cmd_artist_preset(self, event: AstrMessageEvent):
        """画师预设：列出或切换画师风格"""
        argument = event.message_str.removeprefix("nai art").strip()
        session = SessionContext.from_event(event)
        state = self._artist_state_store.get(session)

        if not self._artist_presets:
            yield event.plain_result("当前没有配置画师预设，请管理员在配置中添加。")
            return

        if argument:
            if not argument.isdigit():
                yield event.plain_result("请填写数字编号，例如：nai art 2")
                return
            index = int(argument)
            if not 1 <= index <= len(self._artist_presets):
                yield event.plain_result(
                    f"编号超出范围，当前共有 {len(self._artist_presets)} 个预设。"
                )
                return
            state.selected_artist_index = index
            yield event.plain_result(
                f"已切换到画师预设 #{index}：{self._artist_presets[index - 1].name}"
            )
            return

        current_index = state.selected_artist_index or 1
        lines = [f"当前画师预设：#{current_index}"]
        for i, preset in enumerate(self._artist_presets, start=1):
            marker = "->" if i == current_index else "  "
            desc_part = f" - {preset.description}" if preset.description else ""
            lines.append(f"{marker} {i}. {preset.name}{desc_part}")
        yield event.plain_result("\n".join(lines))

    # ========== nai画图命令（直接调用插件AI） ==========
    
    def _parse_presets_from_params(
        self,
        raw_params: str,
    ) -> tuple[list[str], dict[str, str], list[str], list[tuple[str, str]]]:
        """从参数中解析预设列表和其他参数
        
        Returns:
            (预设名列表按优先级排序, 其他参数字典, cs名称列表, 图片参数)
        """
        import re
        preset_pattern = re.compile(r'^s(\d+)$')
        cs_pattern = re.compile(r'^cs(\d+)$')
        
        presets: list[tuple[int, str]] = []  # (编号, 预设名)
        cs_entries: dict[int, str] = {}
        image_params: list[tuple[str, str]] = []
        other_params: dict[str, str] = {}
        description_lines: list[str] = []
        
        for line in raw_params.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            if '=' in line:
                key, value = line.split('=', 1)
            elif ' ' in line:
                key, value = line.split(' ', 1)
            else:
                description_lines.append(line)
                continue
            key = key.strip()
            value = value.strip()

            if key == "s":
                preset_num = 1
            else:
                match = preset_pattern.match(key)
                preset_num = int(match.group(1)) if match else 0

            if preset_num:
                presets.append((preset_num, value))
                continue

            if key == "cs":
                cs_num = 1
            else:
                cs_match = cs_pattern.match(key)
                cs_num = int(cs_match.group(1)) if cs_match else 0

            if cs_num:
                existing = cs_entries.get(cs_num)
                if existing and existing != value:
                    raise ValueError(f"cs{cs_num} 重复且不一致")
                cs_entries[cs_num] = value
            elif key in {
                "i2i",
                "图生图",
                "vibe_transfer",
                "v_t",
                "氛围转移",
                "character_keep",
                "c_k",
                "ck",
                "角色保持",
            }:
                image_params.append((key, value))
            else:
                other_params[key] = value
        
        # 裸文本直接作为 ds= 描述（不会覆盖显式的 ds=xxx）
        if description_lines and "ds" not in other_params:
            other_params["ds"] = "\n".join(description_lines)
        
        # 按编号排序
        presets.sort(key=lambda x: x[0])
        cs_names = [name for _, name in sorted(cs_entries.items(), key=lambda x: x[0])]
        return [name for _, name in presets], other_params, cs_names, image_params
    
    @filter.command("nai画图")
    async def cmd_nai_draw(self, event: AstrMessageEvent):
        """使用插件 AI 直接画图"""
        async for result in handle_nai_draw(self, event, WAITING_REPLIES):
            yield result

    # ========== 自动画图命令 ==========
    
    @filter.command("nai自动画图关")
    async def cmd_auto_draw_off(self, event: AstrMessageEvent):
        """关闭自动画图"""
        async for result in handle_auto_draw_off(self, event):
            yield result
    
    @filter.command("nai自动画图开")
    async def cmd_auto_draw_on(self, event: AstrMessageEvent):
        """开启自动画图
        
        格式：
        nai自动画图开
        s1=xxx
        s2=xxx
        """
        async for result in handle_auto_draw_on(self, event):
            yield result
    
    @filter.command("nai自动画图")
    async def cmd_auto_draw(self, event: AstrMessageEvent):
        """查看或设置自动画图状态
        
        不带参数：显示当前状态
        带参数：设置预设并开启
        
        格式：
        nai自动画图             → 显示状态
        nai自动画图             → 设置预设（同时开启）
        s1=xxx
        """
        async for result in handle_auto_draw(self, event):
            yield result

    # ========== 画图命令 ==========

    @filter.command(COMMAND)
    async def cmd_nai(self, event: AstrMessageEvent):
        """泡泡画图"""
        raw = event.message_str.removeprefix(COMMAND).strip()
        first_word = raw.split()[0] if raw else ""
        if first_word in {"art"}:
            return
        async for result in handle_cmd_nai(self, event, WAITING_REPLIES):
            yield result

    # ========== 自动画图钩子 ==========
    
    @filter.on_llm_response(priority=50)
    async def on_llm_response_auto_draw(self, event: AstrMessageEvent, resp: LLMResponse):
        """监听主 AI 回复，自动生成图片"""
        await handle_llm_response_auto_draw(self, event, resp)

