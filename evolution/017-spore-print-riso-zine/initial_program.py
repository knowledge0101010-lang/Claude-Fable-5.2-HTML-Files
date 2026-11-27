"""Evolved candidate for 017-spore-print-riso-zine — built from scratch against its spec."""
# EVOLVE-BLOCK-START
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Spore Print — A Two-Colour Zine</title>
</head>
<body>
<canvas id="scene" style="display:block;width:100vw;height:100vh;background:#111"></canvas>
<script>
const c = document.getElementById('scene').getContext('2d');
c.fillStyle = '#888';
c.fillRect(40, 40, 200, 200);
</script>
</body>
</html>
"""
# EVOLVE-BLOCK-END
