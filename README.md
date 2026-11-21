# cairn · 知识体系

cairn 是路标石堆：每个小节是一块石头，逐个累积，为后来者指路。一个不限定学科的知识库：把概念、通用方法、具体模型和原始数据资源串成可学习、可引用的知识网络。按科学问题组织，不按部署接口或本地数据库表组织；当前已建成的脉络集中在生物学、模型方法与数据资源，后续可按同一套骨架扩充到其他领域。

**从[知识总目录](content/README.md)开始。** 当前规划 **28 条知识脉络、1406 个小节**。初始迁移只建立目录任务，全部从 WAITING 开始；后续进度以各系列 README 为准。

## 目录层级

```text
cairn/
├── content/
│   ├── 基础知识/
│   │   ├── 生物学/<系列>/README.md
│   │   └── 模型方法/<系列>/README.md
│   └── 专题知识/
│       ├── 模型/<系列>/README.md
│       └── 数据资源/<系列>/README.md
├── .agents/skills/extend-knowledge/
│   ├── SKILL.md             # 新模型、新原始资源如何扩充目录
│   ├── granularity.md       # 按知识深度和认知负担划定学习单元
│   ├── curriculum.md        # 整合式章节目录：REUSE 在使用处编入专题课程
│   ├── processing.md        # 小节认领、视频成稿与验收方式
│   ├── template.md
│   └── examples.md
├── .agents/skills/review-knowledge-tracks/
│   ├── SKILL.md             # 逐脉络检查主线、顺序、REUSE、标题与目标
│   ├── checklist.md         # 审查清单
│   └── report-template.md   # 单条与批量复审报告模板
├── site/                    # 与 video2blog-content 同源的前端与构建源码
├── vendor/katex/            # 本地公式渲染资源
├── scripts/                 # 目录、状态与公式检查
├── tests/
└── docs/来源说明.md
```

每层都有 README 导航；专题脉络的章节目录本身就是完整课程：所用 B/M 通用知识以 `[REUSE]` 小节在使用处编入，与专题特有小节交错排列，不用自行从整门基础课筛选，也没有另一份“学习路线”。知识正文仍有唯一主归属，复用条目只链接、不复制。目录标题直接列明知识主题与关键知识点，学习问题和深度边界单列在目标中。**100 小节的容量只约束每一条叶子脉络，分类及全项目汇总不受此限制；数量不是需要压低或凑满的目标。**

## 按目标进入

- 建立基础：[生物学](content/基础知识/生物学/README.md)或[模型方法](content/基础知识/模型方法/README.md)。
- 理解具体方法：[模型专题](content/专题知识/模型/README.md)。
- 理解数据对象和证据：[原始数据资源](content/专题知识/数据资源/README.md)。
- 新增模型或站点：[目录扩充 skill](.agents/skills/extend-knowledge/SKILL.md)。
- 检查/复审脉络：[脉络检查 skill](.agents/skills/review-knowledge-tracks/SKILL.md)。
- 处理一个小节：[小节处理规则](.agents/skills/extend-knowledge/processing.md)。
- 查看最新章节整合及历史复审：[章节整合说明](docs/目录审查/2026-11-20-章节整合说明.md)；历史记录及编号链见[目录审查](docs/目录审查/README.md)。
- 了解来源与迁移：[来源说明](docs/来源说明.md)。

项目 skill 位于 `.agents/skills/`，可以由支持项目技能的工具发现；其他工具按 [AGENTS.md](AGENTS.md) 读取即可，无需全局安装。

## 前端构建与预览

采用 video2blog-content 的同一套 MkDocs Material、newsprint 风格、目录树、大纲切换、侧栏拖拽、深浅色、搜索、按需 KaTeX 和视频时间戳就地播放；资源在本项目内，不依赖相邻仓库。

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python site/build_site.py --check
python site/build_site.py
mkdocs serve
```

打开 MkDocs 输出的本地地址。生成静态站：

```bash
mkdocs build --strict
# 输出：build/site/
```

构建链是 `content/ → build/docs + build/nav.yml → build/site`。根 README 是站点首页，`content/README.md` 是知识总目录，各级 README 转为目录索引页；保留跨脉络锚点。不要编辑 `build/`。

未配置远程仓库、正式域名或自动部署；CI 只验证并生成可下载的静态站产物，不沿用来源项目的 GitHub Pages 身份。

## 小节处理方式

README 按“章 → 节 → 小节”组织，小节行尾记录 `[WAITING] → [PROCESSING] → [DONE/ABORT]`。正文物理路径只设“节/小节”，不另建章目录：

```text
<系列>/
├── README.md
└── X.Y_<节名>/
    └── X.Y.Z_<小节名>/
        ├── <博客标题>.md
        └── assets/<博客标题>/
```

1–3 篇是每个小节的默认素材预算，完成以学习目标覆盖为准，不以篇数验收。一篇视频博客只有一个规范位置，但可通过其他小节的目标覆盖导读被复用，避免重复整理同一场报告。下载、字幕、抽帧、图文稿等中间结果放 `_work/`；只有博客、配图与索引进入 `content/`。

```bash
python3 scripts/sections.py list --track B01 --status WAITING
# 明确开始该小节后再认领，以下命令会修改进度：
python3 scripts/sections.py claim --track B01 --section 1.1.1
# 按输出的规范路径写作并验收后，再 finish；不要为演示而认领真实任务。
```

工具提供带旧状态比较与文件锁的精确单行更新；正文存在或导读有真实引用仅满足基本产物检查，不会替代逐项目标的人工验收。具体素材探索、外部 video2blog skill、失败恢复与批量处理边界见项目 skill 的 [processing.md](.agents/skills/extend-knowledge/processing.md)。

## 检查

目录与状态工具只需 Python 3.10+ 标准库；构建需 `requirements.txt`，公式检查需 Node.js 和本地 KaTeX：

```bash
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
python3 site/build_site.py --check
node scripts/check/check_md_math.mjs content
python3 site/build_site.py
mkdocs build --strict
node scripts/check/check_katex.mjs build/site --recursive
```

目录校验覆盖编号、层级、标题、单条 1–99 限制、锚点、链接、统计和前置依赖环；还检查 `[REUSE]` 链接精确到具体小节、不链式复用、不带状态、有学习目标，不得残留独立学习路线，以及 DONE 的材料存在性。标题检测只排查明显句式，内容是否明确仍须人工审查。测试中的构建器测试需先安装站点依赖。静态检查不验证外站、科学事实、素材质量或许可。

## 边界

cairn 的初始内容从 protenix 的知识目录迁出，独立维护；不承载推理服务、原始实验数据或业务接口。目录骨架与学科无关：新增领域只需在 `content/` 下按“基础知识／专题知识”的同一套约定扩展，不必改动构建与校验链。数据专题以原始提供方和官方发布为主体，不把 biodata 的二次加工站点当作原始数据库。

站点组件取自 video2blog-content，未复制其博客、工作缓存、cookies、账号或视频下载材料；来源记录见项目说明。逐来源保留署名并核对许可，不为内部实验和第三方材料推断统一授权。
