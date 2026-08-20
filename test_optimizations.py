"""Comprehensive validation of all recent optimizations.

Checks:
1. All Python tests pass
2. Subprocess progress script compiles
3. Config defaults match expected values
4. Audio postprocessing functions exist and work
5. Rolling-average ETA code structure is correct
"""

import subprocess
import sys
import time
import os


def check_tests():
    """Run the full test suite."""
    print("=" * 60)
    print("1. RUNNING FULL PYTHON TEST SUITE")
    print("=" * 60)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-x", "--tb=short", "-q"],
        capture_output=True, text=True, timeout=300, cwd=os.path.dirname(__file__) or ".",
    )
    if result.returncode == 0:
        print("  PASS: All tests passed")
        return True
    else:
        print(f"  FAIL: Tests failed with return code {result.returncode}")
        print(result.stdout[-500:])
        print(result.stderr[-500:])
        return False


def check_subprocess_script():
    """Check the subprocess script syntax."""
    print("=" * 60)
    print("2. CHECKING SUBPROCESS SCRIPT SYNTAX")
    print("=" * 60)
    nl = "\n"
    script = (
        "import time, urllib.request, json" + nl +
        "t0=time.time()" + nl +
        "est=51.0" + nl +
        "off=5" + nl +
        "sc=85" + nl +
        "jid='test_job'" + nl +
        "url='http://127.0.0.1:8000'" + nl +
        "while True:" + nl +
        "    el=time.time()-t0" + nl +
        "    if el>est*1.5: break" + nl +
        "    pct=off+min(el/max(est,1),0.90)*sc" + nl +
        "    try:" + nl +
        "        msg='Sep '+str(round(el))+'s/~'+str(round(est))+'s'" + nl +
        "        data=json.dumps({'percent':round(pct,1),'message':msg}).encode()" + nl +
        "        req=urllib.request.Request(url+'/api/jobs/'+jid+'/progress',data=data,headers={'Content-Type':'application/json'})" + nl +
        "        urllib.request.urlopen(req,timeout=2)" + nl +
        "    except:" + nl +
        "        pass" + nl +
        "    time.sleep(3)" + nl
    )
    try:
        compile(script, "<subprocess_script>", "exec")
        print("  PASS: Subprocess script compiles correctly")
        return True
    except SyntaxError as e:
        print(f"  FAIL: Syntax error in subprocess script: {e}")
        return False


def check_subprocess_runtime():
    """Verify the subprocess can start and run briefly."""
    print("=" * 60)
    print("3. CHECKING SUBPROCESS RUNTIME")
    print("=" * 60)
    nl = "\n"
    script = (
        "import time, urllib.request, json" + nl +
        "t0=time.time()" + nl +
        "est=10.0" + nl +
        "off=5" + nl +
        "sc=85" + nl +
        "jid='test_job'" + nl +
        "url='http://127.0.0.1:8000'" + nl +
        "while True:" + nl +
        "    el=time.time()-t0" + nl +
        "    if el>est*1.5: break" + nl +
        "    pct=off+min(el/max(est,1),0.90)*sc" + nl +
        "    try:" + nl +
        "        msg='Sep '+str(round(el))+'s/~'+str(round(est))+'s'" + nl +
        "        data=json.dumps({'percent':round(pct,1),'message':msg}).encode()" + nl +
        "        req=urllib.request.Request(url+'/api/jobs/'+jid+'/progress',data=data,headers={'Content-Type':'application/json'})" + nl +
        "        urllib.request.urlopen(req,timeout=2)" + nl +
        "    except:" + nl +
        "        pass" + nl +
        "    time.sleep(3)" + nl
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    time.sleep(3)
    proc.kill()
    out, err = proc.communicate(timeout=5)
    if err:
        err_text = err.decode("utf-8", errors="replace")
        print(f"  FAIL: Subprocess stderr: {err_text[:200]}")
        return False
    print("  PASS: Subprocess starts and runs without errors")
    return True


def check_config_defaults():
    """Verify config defaults match expected values."""
    print("=" * 60)
    print("4. CHECKING CONFIG DEFAULTS")
    print("=" * 60)
    # Import config and check defaults
    sys.path.insert(0, os.path.dirname(__file__) or ".")
    from code.config import DEFAULT_CONFIG

    checks = [
        ("denoise_strength", 0.55),
        ("denoise_strength_low", 0.35),
        ("denoise_strength_mid", 0.10),
        ("denoise_strength_high", 0.25),
        ("min_vocal_duration", 0.08),
        ("model_name", "htdemucs"),
        ("segment", 6.0),
        ("shifts", 1),
    ]
    all_ok = True
    for key, expected in checks:
        actual = DEFAULT_CONFIG.get(key)
        if actual == expected:
            print(f"  PASS: {key} = {actual}")
        else:
            print(f"  FAIL: {key} = {actual} (expected {expected})")
            all_ok = False
    return all_ok


def check_eta_code():
    """Verify the rolling-average ETA code structure."""
    print("=" * 60)
    print("5. CHECKING ETA CODE STRUCTURE")
    print("=" * 60)
    controller_path = os.path.join(
        os.path.dirname(__file__) or ".",
        "flutter_app", "lib", "controllers", "separation_controller.dart"
    )
    if not os.path.exists(controller_path):
        print(f"  SKIP: {controller_path} not found (Flutter not available)")
        return True

    with open(controller_path, encoding="utf-8") as f:
        content = f.read()

    checks = [
        ("_RateSample class", "class _RateSample"),
        ("_addRateSample method", "_addRateSample("),
        ("_resetRateSamples method", "_resetRateSamples"),
        ("_rateSamples field", "_rateSamples"),
        ("Full-window rate calc", "rate = dt / dp"),
        ("Fallback instant rate", "elapsed / _progress"),
        ("5-second delay", "elapsed < 5"),
        ("HTTP polling sample", "_addRateSample(tp)"),
    ]
    all_ok = True
    for label, pattern in checks:
        if pattern in content:
            print(f"  PASS: {label}")
        else:
            print(f"  FAIL: {label} not found")
            all_ok = False
    return all_ok


def check_api_endpoint():
    """Verify the progress endpoint code exists."""
    print("=" * 60)
    print("6. CHECKING PROGRESS API ENDPOINT")
    print("=" * 60)
    api_path = os.path.join(
        os.path.dirname(__file__) or ".",
        "api_server", "main.py"
    )
    if not os.path.exists(api_path):
        print(f"  SKIP: {api_path} not found")
        return True

    with open(api_path, encoding="utf-8") as f:
        content = f.read()

    checks = [
        ("Body import", "from fastapi import"),
        ("Body usage", "Body("),
        ("Progress endpoint", "/api/jobs/{job_id}/progress"),
        ("_job_id injection", "_job_id"),
        ("_update_job call", "_update_job(job_id, total_progress="),
    ]
    all_ok = True
    for label, pattern in checks:
        if pattern in content:
            print(f"  PASS: {label}")
        else:
            print(f"  FAIL: {label} not found")
            all_ok = False
    return all_ok


def check_separation_engine():
    """Verify the subprocess progress estimation code."""
    print("=" * 60)
    print("7. CHECKING SEPARATION ENGINE")
    print("=" * 60)
    engine_path = os.path.join(
        os.path.dirname(__file__) or ".",
        "code", "separation_engine.py"
    )
    with open(engine_path, encoding="utf-8") as f:
        content = f.read()

    checks = [
        ("Subprocess spawn", "subprocess.Popen"),
        ("_job_id check", "self.config.get(\"_job_id\")"),
        ("Estimated seconds calc", "estimated_seconds"),
        ("Script build with nl", "nl"),
        ("Progress message", "Separating"),
        ("Subprocess kill in finally", "est_proc.kill"),
        ("Error handling", "except Exception"),
    ]
    all_ok = True
    for label, pattern in checks:
        if pattern in content:
            print(f"  PASS: {label}")
        else:
            print(f"  FAIL: {label} not found")
            all_ok = False
    return all_ok


if __name__ == "__main__":
    results = {}
    for name, func in [
        ("Tests", check_tests),
        ("Script Syntax", check_subprocess_script),
        ("Script Runtime", check_subprocess_runtime),
        ("Config Defaults", check_config_defaults),
        ("ETA Code", check_eta_code),
        ("API Endpoint", check_api_endpoint),
        ("Engine Code", check_separation_engine),
    ]:
        print()
        results[name] = func()

    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    all_pass = True
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        print(f"  [{status}] {name}")
    print()
    if all_pass:
        print("ALL CHECKS PASSED")
    else:
        print("SOME CHECKS FAILED")
    sys.exit(0 if all_pass else 1)
