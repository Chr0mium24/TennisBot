# YOLO 0260701 Backup Dataset Merge

日期：2026-07-03

## 目标

把本机备份 `/home/cr/Codes/TennisBot_backups/tools_yolo_0260701_20260703_104852.tar`
中的 0260701 图片和标签合并到当前 YOLO workspace 数据集。

## 计划

1. 只检查 tar 目录结构，不全量解包。
2. 确认备份中的 `0260701/images` 和 `0260701/labels` 数量。
3. 只抽取 `images` 和 `labels`，不解 `images.zip`。
4. 合并到 `tools/yolo/workspace/dataset/images/0260701` 和
   `tools/yolo/workspace/dataset/labels/0260701`。
5. 校验标签是否有对应图片。
6. 重新运行 `sprites extract`，为新增标签生成候选 sprite。

## 结果

- 备份 tar 大小：`23G`。
- 备份中 `0260701/images` 图片数：`17768`。
- 备份中 `0260701/labels` 标签数：`4`。
- 合并后 workspace 数据集图片数：`17900`。
- 合并后 workspace 数据集标签文件数：`665`。
- 4 个新增标签都能找到对应图片。
- `sprites extract` 后候选总数：`113`。
- 当前候选状态：`109 approved`，`4 candidate`。

## 验证结果

```bash
tar -tf /home/cr/Codes/TennisBot_backups/tools_yolo_0260701_20260703_104852.tar
find tools/yolo/workspace/dataset/images/0260701 -maxdepth 1 -type f | wc -l
find tools/yolo/workspace/dataset/labels/0260701 -maxdepth 1 -type f | wc -l
bun scripts/yolo.ts sprites extract
curl -fsS http://127.0.0.1:8766/api/sprites
```

- `sprites extract` 输出：`candidates=113`，`skipped_images=17787`。
- 审核服务 `/api/sprites` 返回 `113` 个 sprite。
- 数据集和生成产物都位于 ignored `tools/yolo/workspace/`，不会进入 Git。
