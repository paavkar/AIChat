from django.shortcuts import render
import json
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt  # Disable CSRF for simplicity here
import redis.asyncio as redis
from asgiref.sync import sync_to_async


# Create your views here.

# Create a Redis connection (using async Redis client)
redis_conn = redis.Redis(host="localhost", port=6379, db=0)

async def display_config_view(request):
    # Await the async function to get the current configuration
    config = await get_current_config()
    # Wrap the synchronous render call so that it can be awaited
    response = await sync_to_async(render)(
        request,
        'botconfig/config.html',
        {'config': config}
    )
    return response

async def get_current_config():
    """Retrieve the current configuration from Redis or return fallback defaults."""
    config_json = await redis_conn.get("bot_config")
    if config_json:
        return json.loads(config_json)
    return {"timeout_duration": 600, "discord_actions_enabled": True}

async def update_config(new_config):
    """Update the configuration in Redis and publish the update."""
    current_config = await get_current_config()
    current_config.update(new_config)
    config_json = json.dumps(current_config)
    await redis_conn.set("bot_config", config_json)
    await redis_conn.publish("config_updates", config_json)

    return current_config

@csrf_exempt  # Disable CSRF for this demo endpoint (consider proper CSRF handling in production)
async def update_config_view(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Method not allowed."}, status=405)
    try:
        # Decode and parse the request body from JSON.
        new_settings = json.loads(request.body.decode("utf-8"))
        updated_config = await update_config(new_settings)

        return JsonResponse({"status": "success", "config": updated_config}, status=200)
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

async def get_config_view(request):
    """Endpoint to get the current configuration."""
    config = await get_current_config()

    return JsonResponse({"status": "success", "config": config}, status=200)
