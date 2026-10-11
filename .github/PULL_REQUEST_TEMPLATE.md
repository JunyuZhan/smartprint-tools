# Pull Request

## 变更内容
简要描述本次改动做了什么。

## 为什么需要这个变更
关联 Issue（如有）：`Fixes #<issue>` / `Closes #<issue>`

## 验证方式
- [ ] 本地 `python -m pytest tests -v` 全部通过（Windows）
- [ ] `python -m compileall -q smartprint server.py tests` 无错误
- [ ] CI 两个 job（Linux 测试 + Windows 打包）全绿
- [ ] 涉及用户可见行为时，README / CHANGELOG 已同步更新

## 测试覆盖
列出为本次改动新增/修改的测试：
- `tests/...`：覆盖了……

## 备注
其他需要 reviewer 注意的点。
