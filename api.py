from flask import Flask, request, jsonify
import redis.asyncio as redis
import json
from constants import BOT_CONFIG_KEY

app = Flask(__name__)
redis_conn = redis.Redis(host="localhost", port=6379, db=0)

async def get_current_config():
    """Retrieve the current configuration from Redis."""
    # Assume the configuration is stored as a JSON string.
    config_json = await redis_conn.get(BOT_CONFIG_KEY)
    if config_json:
        return json.loads(config_json)
    # Fallback defaults.
    return {"timeout_duration": 600, "discord_actions_enabled": True}

async def update_config(new_config):
    """Update the configuration in Redis and publish the update."""
    current_config = await get_current_config()
    current_config.update(new_config)
    config_json = json.dumps(current_config)
    await redis_conn.set(BOT_CONFIG_KEY, config_json)
    # Publish to the config_updates channel.
    await redis_conn.publish("config_updates", config_json)
    return current_config

@app.route("/update_config", methods=["POST"])
async def update_config_endpoint():
    try:
        # Expects a JSON with the configuration changes.
        new_settings = request.json
        updated_config = update_config(new_settings)
        return jsonify({"status": "success", "config": updated_config}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# Optionally expose an endpoint to get current configuration.
@app.route("/get_config", methods=["GET"])
async def get_config_endpoint():
    config = await get_current_config()
    return jsonify({"status": "success", "config": config}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)