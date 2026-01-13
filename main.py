from flask import Flask
from lovart_routes import lovart_bp

app = Flask(__name__)

# 注册蓝图
app.register_blueprint(lovart_bp)

if __name__ == '__main__':
    import os
    host = os.environ.get('HOST', '0.0.0.0')
    port = 5005
    # 默认关闭 Debug 模式以用于生产环境，除非环境变量显式开启
    debug = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 'yes')
    
    print(f"Starting server on {host}:{port} (Debug: {debug})")
    app.run(host=host, port=port, debug=debug)