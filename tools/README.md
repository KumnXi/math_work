# tools/ 通用脚本

与 skill 解耦的通用分析工具，求解代码可 `sys.path.insert` 复用。

| 脚本 | 用途 | 用法 |
|---|---|---|
| `figure_style.py` | matplotlib 统一风格（中文 SimHei + 论文配色 + 300dpi） | `import figure_style as fs; fig, ax = fs.new_axes(); fs.save(fig, path)` |
| `eval_metrics.py` | MAE / RMSE / MAPE / R² | `from eval_metrics import metrics_report; metrics_report(y, yhat)` |
| `preprocess.py` | CSV/Excel 数据 EDA 报告 | `$PYTHON_EXE preprocess.py data.csv [--out rep.md]` |
| `sensitivity.py` | 单变量 OAT 灵敏度分析 + tornado | `$PYTHON_EXE sensitivity.py --func mymod:obj --base base.json` |
| `generate_docx.py` | 完整版 Word：pandoc 转 main.tex → main.docx（公式原生可编辑 OMML、图/表带编号引用） | `$PYTHON_EXE generate_docx.py <task_dir>`（依赖 pandoc，见 `config/machine.json` 的 `PANDOC_EXE`） |

## sensitivity.py 示例

模型函数（求解代码里）：
```python
# mymod.py
def obj(params):
    a, b, x = params["a"], params["b"], params["x"]
    return a * x + b * x**2
```
基准参数 `base.json`：
```json
{"a": 2.0, "b": 0.1, "x": 5.0}
```
运行：
```bash
"$PYTHON_EXE" tools/sensitivity.py --func mymod:obj --base base.json
```
输出各参数 ±10%/±20% 的目标变化与敏感性指数（>0.5 视为敏感）。
