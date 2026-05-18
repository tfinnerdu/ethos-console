import json
import time
from flask import Blueprint, Response, jsonify, request, current_app, stream_with_context
from app import get_monitor

bus_bp = Blueprint("bus", __name__)


@bus_bp.get("/stream")
def bus_stream():
    monitor = get_monitor(current_app._get_current_object())

    def generate():
        last_index = 0
        while True:
            events, total = monitor.get_events(since_index=last_index)
            for event in events:
                yield f"data: {json.dumps(event)}\n\n"
            last_index = total

            depth = monitor.queue_depth
            last_poll = monitor.last_poll
            meta = {
                "type": "meta",
                "queue_depth": depth,
                "last_poll": round(time.time() - last_poll) if last_poll else None,
                "paused": monitor.paused,
            }
            yield f"data: {json.dumps(meta)}\n\n"
            time.sleep(0.5)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@bus_bp.get("/stats")
def bus_stats():
    monitor = get_monitor(current_app._get_current_object())
    return jsonify({
        "queue_depth": monitor.queue_depth,
        "paused": monitor.paused,
        "resource_stats": monitor.get_resource_stats(),
        "last_poll_seconds_ago": round(time.time() - monitor.last_poll) if monitor.last_poll else None,
        "buffer_size": len(monitor.event_buffer),
    })


@bus_bp.post("/pause")
def pause():
    monitor = get_monitor(current_app._get_current_object())
    monitor.pause()
    return jsonify({"paused": True})


@bus_bp.post("/resume")
def resume():
    monitor = get_monitor(current_app._get_current_object())
    monitor.resume()
    return jsonify({"paused": False})


@bus_bp.post("/clear")
def clear():
    monitor = get_monitor(current_app._get_current_object())
    monitor.clear()
    return jsonify({"cleared": True})


@bus_bp.get("/export")
def export():
    monitor = get_monitor(current_app._get_current_object())
    limit = int(request.args.get("limit", 100))
    events = monitor.export_events(limit=limit)
    lines = []
    for e in events:
        if e.get("type") == "error":
            lines.append(f"{e.get('timestamp', '')}  ERROR  {e.get('message', '')}")
        else:
            lines.append(
                f"{e.get('timestamp', '')}  {e.get('resource', ''):<40}  "
                f"{e.get('operation', ''):<10}  {e.get('guid', ''):<40}  id:{e.get('id', '')}"
            )
    text = "\n".join(lines)
    return Response(
        text,
        mimetype="text/plain",
        headers={"Content-Disposition": "attachment; filename=ethos-bus-export.txt"},
    )
