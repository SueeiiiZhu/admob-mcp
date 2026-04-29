# AdMob v1beta API 限制清单

记录在测试 v1beta 写接口时实测发现的接口缺口与字段限制。来源：discovery doc + 实际 RPC 错误。
官方文档对这些大多语焉不详，做需求评估前先查这份清单。

校验当前 discovery doc 的脚本：

```bash
python3 -c "import urllib.request, json; \
  data = json.loads(urllib.request.urlopen('https://admob.googleapis.com/\$discovery/rest?version=v1beta').read()); \
  print(json.dumps(data['resources']['accounts']['resources'], indent=2))" \
  | grep -E '"(methods|create|list|get|patch|delete|stop|batchCreate)"'
```

## 1. 完全没有的方法

| 资源 | 暴露的方法 | **缺失的方法** | 影响 |
|---|---|---|---|
| `mediationAbExperiments` | `create`, `stop` | `list` / `get` / `delete` | 无法实现 `list_mediation_ab_experiments` MCP 工具；事后查实验状态只能走 AdMob 控制台或 `AD_SOURCE_INSTANCE` 维度的报表 |
| `adUnitMappings` | `create`, `batchCreate`, `list` | `update` / `delete` | 测试残留只能在 AdMob 控制台手动删（参考 issue #1） |
| `mediationGroups` | `list`, `create`, `update` | `delete` | 测试用 group 同样无法删除，建议测试时 displayName 加 `_DELETE_ME` 标记 |

> v1（非 beta）API 覆盖更少：`mediationAbExperiments` 资源在 v1 完全不存在。

## 2. `mediationGroups.list` 的 filter 限制

服务端 `filter` 仅支持以下三个字段：

- `STATE`
- `PLATFORM`
- `FORMAT`

**会被拒**为 `Invalid field name` 的字段：

- `AD_UNIT_ID`
- `MEDIATION_GROUP_ID`
- `displayName`

`displayName` 过滤只能客户端做。本仓库 `list_mediation_groups` 提供 `display_name_contains` 参数，逐页过滤、`max_items` 计后置命中数。

## 3. `mediationGroups.patch` 的 update_mask 限制

只允许 patch 这些顶层字段：

- `displayName`
- `state`
- `targeting`

`mediationGroupLines` **不能**通过 PATCH 修改（mask 里出现该字段会报 *"Update mask contains fields that do not exist..."*）。

要改 lines，必须走：
1. `create_mediation_ab_experiment` 创建实验，treatment 写新 lines
2. `stop_mediation_ab_experiment(variant_choice="VARIANT_CHOICE_B")` 把 treatment 写回 group

## 4. `adUnitMappings` 字段坑

- `state` 只接受 `"ENABLED"`，传 `"DISABLED"` 会被拒为 invalid enum
- `batchCreate` 请求项字段名是 `parent`（**不是** `adUnitId`），形如 `accounts/pub-XXX/adUnits/123`
- 按 (`adapterId` + `adUnitConfigurations`) 去重：配置完全相同的二次创建会复用旧 mapping id 仅更新 displayName，不创建新行

## 5. `mediationAbExperiments` 字段坑

### `create` 请求
- `controlMediationLines` 是 **readOnly**：AdMob 自动从 parent group 当前 lines 继承，body 里写它会报 unknown field
- `treatmentMediationLines` 是 **list**（不是 map），且每条**必须**包一层 `mediationGroupLine`：
  ```json
  [{"mediationGroupLine": {"displayName": "...", "adSourceId": "...", "cpmMode": "LIVE", "state": "ENABLED"}}]
  ```
- treatment line **不能**写 `id`，AdMob 自动生成；写了会报 *"Treatment mediation lines shouldn't specify an Id"*
- `treatmentTrafficPercentage` 是字符串 `"1"`–`"99"`

### `stop` 请求
- 路径只到集合层 `accounts/{aid}/mediationGroups/{gid}/mediationAbExperiments`，**不带** experiment id（每个 group 同时只允许一个实验）
- `variantChoice` 枚举值是：
  - `VARIANT_CHOICE_A`：保留对照组
  - `VARIANT_CHOICE_B`：采用实验组写回 group
  - 文档里偶尔出现的 `CHOOSE_CONTROL` / `CHOOSE_TREATMENT` 是错的

## 6. 写权限的 OAuth scope

读接口够用 `admob.readonly` 就行；以下接口必须额外授权 `admob.monetization`：

- `mediationGroups`：`create`, `update`
- `mediationAbExperiments`：`create`, `stop`
- `adUnitMappings`：`create`, `batchCreate`

只有 readonly token 时调写接口会报 `403 insufficient_scopes`。换 scope 重跑 `auth_flow.py` 重新授权。
