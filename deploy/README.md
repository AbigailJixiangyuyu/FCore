# 在远程 Ubuntu 服务器部署 FCore

适用环境为 Ubuntu 24.04.4 LTS、`x86_64` 和 Linux Docker Engine。部署包包含已构建的网页、后端代码、EmailDept3 与合成样例、当前使用的模型权重，以及并行核分解的编译源码。服务器上的 Docker 负责构建镜像并运行 FastAPI。首次构建需能访问 Docker Hub、Debian 软件源、PyPI 和 PyTorch CPU 下载源。

## 上传部署包

将 `fcore-linux-amd64.tar.gz` 上传到远程服务器的登录目录。也可以在 Windows 项目的 `demo` 目录运行以下命令，将 `YOUR_SERVER` 换成可访问的 SSH 地址或现有 SSH 别名。

```powershell
scp .\exports\fcore-linux-amd64.tar.gz root@YOUR_SERVER:~/
```

## 在远程服务器构建并启动

```bash
cd ~
tar -xzf fcore-linux-amd64.tar.gz
cd fcore-cpu
docker build -t fcore:cpu .
cp -n fcore.env.example fcore.env
```

如需使用 LLM-Assisted Interpretation，在服务器的 `fcore.env` 中填写自己的 `LLM_API_KEY`。留空也可以使用历史挖掘、当前查询、SLADE 评分和 Zebra 预测。

```bash
docker run -d --name fcore --restart unless-stopped \
  --env-file ./fcore.env \
  -p 127.0.0.1:8000:8000 \
  -v fcore-data:/opt/fcore/data \
  fcore:cpu
docker logs --tail 30 fcore
curl -fsS http://127.0.0.1:8000/api/health
```

上述端口绑定适合通过 SSH 查看演示。在自己电脑上运行 `ssh -L 18000:127.0.0.1:8000 root@YOUR_SERVER`，保持连接并打开 `http://127.0.0.1:18000`。如需让服务器网络内的其他人直接访问，启动时使用 `-p 8000:8000`，并在服务器防火墙或安全组中对目标访问者开放该端口。

命名卷 `fcore-data` 首次使用时会获得内置数据集，后续保留用户在网页上上传的数据。DeepSeek 设置在进程启动时读取。修改环境文件或更新镜像后，运行 `docker stop fcore`、`docker rm fcore`，再用上面的命令和原数据卷启动新容器。

## 检查功能

- 打开 EmailDept3，执行当前 S12 的并行核分解，`q=49, k=7` 应显示 30 个节点和 145 条内部边。
- 查看异常排名。SLADE 为 S12 的 88 个节点生成分数。用 Zebra 预测 S13，`q=49, k=4`、连边阈值 0.50 应返回 23 个成员。包内同时包含 S14 和 S15 的模型。
- 如需查看实际安装的推理版本，运行 `docker exec fcore python -c "import torch; print(torch.__version__, torch.version.cuda)"`，CPU 版输出 `2.8.0+cpu None`。

## 从项目重新打包

在开发机的 `demo/` 下安装前端依赖后运行打包脚本。脚本会构建 Vue、核对已启用权重的 SHA-256，并将部署包写入 `exports/`。编译并行核使用仓库内的 `backend/vendor/parallel-kcore` 中的头文件。Windows 开发环境的训练入口继续使用 GPU，服务进程可通过 `FCORE_DEVICE=cpu` 选择 CPU 推理。

```powershell
npm --prefix frontend ci
python deploy/package.py
```
