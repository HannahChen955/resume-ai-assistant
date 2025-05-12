from weaviate.connect.helpers import connect_to_local

print("✅ 正在尝试连接 Weaviate...")
client = connect_to_local(host="localhost", port=8080, grpc_port=50051)

print("✅ client.is_ready():", client.is_ready())
print("📦 collections.list_all():", client.collections.list_all())

client.close()  # ✅ 防止资源警告 