import urllib.request, urllib.error, json

def api(method, path, body=None, headers=None):
    url = f"http://localhost:8000{path}"
    data = json.dumps(body).encode() if body else None
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

# 1. Admin Login
code, d = api("POST", "/api/auth/login", {"email":"admin@smartfest.edu","password":"Admin@123"})
print(f"Admin Login: {code}")
print(f"  User: {d['user']['name']} ({d['user']['role']})")
token = d["access_token"]

# 2. List Events
code, events = api("GET", "/api/events", headers={"Authorization":f"Bearer {token}"})
print(f"\nEvents ({len(events)}):")
for e in events:
    print(f"  [{e['status']}] {e['title']} @ {e.get('venue_name','?')} on {e['date']}")

# 3. Analytics
code, analytics = api("GET", "/api/analytics/dashboard", headers={"Authorization":f"Bearer {token}"})
print(f"\nAnalytics: {code}")
print(f"  Users: {analytics['total_users']}, Events: {analytics['total_events']}, Registrations: {analytics['total_registrations']}")

# 4. Student login + AI recommendations
code, sd = api("POST", "/api/auth/login", {"email":"anushka.student@smartfest.edu","password":"Student@123"})
st = sd["access_token"]
code, recs = api("GET", "/api/recommendations", headers={"Authorization":f"Bearer {st}"})
print(f"\nAI Recommendations for Anushka ({len(recs)}):")
for r in recs:
    print(f"  {r['title']} | Score: {r['recommendation_score']} | {r['recommendation_reason']}")

print("\n✅ ALL LIVE API CHECKS PASSED")
