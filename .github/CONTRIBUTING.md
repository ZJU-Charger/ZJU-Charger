# 贡献指南

感谢您对 ZJU Charger 项目的关注！我们欢迎所有形式的贡献。

## 如何贡献

### 报告问题

如果您发现了 bug 或有功能建议，请：

1. 检查 [Issues](https://github.com/Phil-Fan/ZJU-Charger/issues) 中是否已有相关问题
2. 如果没有，请使用相应的 Issue 模板创建新问题
3. 提供清晰的问题描述和复现步骤

### 提交代码

1. **Fork 项目**

   ```bash
   git clone https://github.com/Phil-Fan/ZJU-Charger.git
   cd ZJU-Charger
   ```

2. **创建分支**

   ```bash
   git checkout -b feature/your-feature-name
   # 或
   git checkout -b fix/your-bug-fix
   ```

3. **进行更改**
   - 编写代码
   - 添加测试（如果适用）
   - 更新文档
   - 确保代码通过 lint 检查

4. **提交更改**

   ```bash
   git add .
   git commit -m "feat: 添加新功能描述"
   ```

   提交信息格式：
   - `feat:` 新功能
   - `fix:` 修复 bug
   - `docs:` 文档更新
   - `style:` 代码格式调整
   - `refactor:` 代码重构
   - `test:` 测试相关
   - `chore:` 构建/工具相关

5. **推送并创建 Pull Request**

   ```bash
   git push origin feature/your-feature-name
   ```

   然后在 GitHub 上创建 Pull Request。

## 代码规范

### Markdown 文档

- 使用 markdownlint 检查格式
- 保持文档清晰、简洁
- 添加适当的代码示例

## 行为准则

请遵循我们的 [行为准则](./CODE_OF_CONDUCT.md)。

感谢您的贡献！
