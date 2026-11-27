"""Evolved candidate: a rose-window study built from scratch against 030's spec.

Starts as a bare stub, so the score has room to move. The evaluator scores the
HTML string against harness/spec.py and structural gates; promotion into
studies/ only happens if the evolved candidate clears the original's score.
"""

# EVOLVE-BLOCK-START
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rose Window</title>
</head>
<body>
<canvas id="scene" style="display:block;width:100vw;height:100vh;background:#08070A"></canvas>
<script>
const c = document.getElementById('scene').getContext('2d');
c.fillStyle = '#B3202A';
c.beginPath(); c.arc(200, 200, 80, 0, Math.PI * 2); c.fill();
</script>
</body>
</html>
"""
# EVOLVE-BLOCK-END
