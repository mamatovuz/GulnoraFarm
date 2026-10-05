"""Mini app server testi: vaqtinchalik baza + haqiqiy aiohttp handlerlar (Telegram bot kerak emas).

Ishga tushirish:  python tests/smoke_test.py
"""
import os, sys, asyncio, tempfile, json, time, base64
from types import SimpleNamespace
TMP = tempfile.mkdtemp()
os.environ["BOT_TOKEN"] = "123456:TESTTOKEN"
os.environ["DB_PATH"] = os.path.join(TMP, "t.db")
os.environ["ADMIN_IDS"] = "111"
os.environ["SUPER_ADMIN_ID"] = "111"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from aiohttp.test_utils import TestServer, TestClient
import webapp
from database.db import init_db
from database import queries as q

OK = 0
FAIL = 0
def check(name, cond, extra=""):
    global OK, FAIL
    if cond: OK += 1; print("  ✓", name)
    else: FAIL += 1; print("  ✗", name, extra)


async def main():
    await init_db()
    db = await q.get_db()
    # ma'lumotlar
    await db.execute("INSERT INTO users (telegram_id, full_name, phone, registered_at) VALUES (5001, \"Ra'no O'g'iloy\", '+998901112233', '2026-01-01 10:00:00')")
    await db.commit()
    op_id = await q.add_operator("Ali", "ali", "1234")
    await db.execute("UPDATE operators SET password_hash=? WHERE id=?", (q._legacy_hash("1234"), op_id))  # eski xesh
    await db.execute("UPDATE operators SET work_start='00:00', work_end='23:59' WHERE id=?", (op_id,))
    op2 = await q.add_operator("Vali", "vali", "9999")
    await db.execute("UPDATE operators SET work_start='00:00', work_end='23:59', telegram_id=777 WHERE id=?", (op2,))
    await db.commit()
    oid = await q.create_order(5001, None, "text")
    await q.claim_order(oid, op_id)
    m1 = await q.add_message(oid, "client", "text", "Salom, dori bormi?", None, 10)
    m2 = await q.add_message(oid, "client", "text", "qalin", None, 11, html="<b>qalin</b>")
    old_wait = (webapp.now_local() - webapp.timedelta(minutes=25)).strftime("%Y-%m-%d %H:%M:%S")
    await db.execute("UPDATE messages SET created_at=? WHERE id=?", (old_wait, m2))
    await db.commit()

    cli = TestClient(TestServer(webapp.build_app()))
    await cli.start_server()
    try:
        print("LOGIN")
        r = await (await cli.post("/api/login", json={"login": "ali", "password": "xato"})).json()
        check("xato parol rad etiladi", not r["ok"])
        for _ in range(5):
            await cli.post("/api/login", json={"login": "brute", "password": "x"})
        r = await (await cli.post("/api/login", json={"login": "brute", "password": "x"})).json()
        check("rate-limit ishlaydi", "Juda ko'p" in (r.get("error") or ""), r)
        r = await (await cli.post("/api/login", json={"login": "ali", "password": "1234"})).json()
        check("to'g'ri login", r["ok"], r)
        tok = r["token"]; mk = r["mk"]
        op = await q.get_operator(op_id)
        check("eski xesh pbkdf2 ga yangilandi", op["password_hash"].startswith("pbkdf2$"))
        check("token v2 formatida", tok.startswith("v2."))
        A = {"operator_id": op_id, "token": tok}
        r = await cli.get("/api/chats", params={"operator_id": op_id, "token": "eski-token"})
        check("noto'g'ri token 401", r.status == 401)

        print("CHATS / SYNC")
        r = await (await cli.get("/api/chats", params=A)).json()
        check("chatlar ro'yxati", r["ok"] and r["chats"][0]["name"] == "Ra'no O'g'iloy", r)
        check("o'qilmagan = 2", r["chats"][0]["unread"] == 2, r["chats"][0])
        check("20 daqiqadan oshgan javobsiz chat qizil ogohlantirishga tayyor",
              r["chats"][0]["waiting_min"] >= 20, r["chats"][0])
        r = await (await cli.get("/api/messages", params={**A, "order_id": oid, "mark": 1})).json()
        check("xabarlar + html", r["ok"] and r["messages"][1]["html"] == "<b>qalin</b>", r)
        check("last_read_mid qaytadi", "last_read_mid" in r)
        r = await (await cli.get("/api/chats", params=A)).json()
        check("mark=1 dan keyin o'qilmagan = 0", r["chats"][0]["unread"] == 0, r["chats"][0])
        v = q.change_ver()
        t0 = time.time()
        async def later():
            await asyncio.sleep(0.6)
            await q.add_message(oid, "client", "text", "yangi xabar", None, 12)
        asyncio.create_task(later())
        r = await (await cli.get("/api/sync", params={**A, "v": v, "order_id": oid, "after": m2})).json()
        dt = time.time() - t0
        check("long-poll o'zgarishda darhol uyg'onadi", 0.4 < dt < 5, dt)
        check("sync yangi xabarni beradi", r["ok"] and [m["text"] for m in r["chat"]["messages"]] == ["yangi xabar"], r.get("chat"))
        check("sync media kaliti beradi", bool(r.get("mk")))

        print("OPERATOR HUQUQLARI")
        op2_login = await (await cli.post("/api/login", json={"login": "vali", "password": "9999"})).json()
        A_OTHER = {"operator_id": op2, "token": op2_login["token"]}
        resp = await cli.get("/api/messages", params={**A_OTHER, "order_id": oid})
        check("boshqa operator yozishmani ko'ra olmaydi", resp.status == 403, resp.status)
        resp = await cli.post("/api/send", json={**A_OTHER, "order_id": oid, "text": "begona"})
        check("boshqa operator mijozga yoza olmaydi", resp.status == 403, resp.status)
        r = await (await cli.get("/api/general_chats", params=A_OTHER)).json()
        check("umumiyda barcha jarayondagi chatlar ko'rinadi",
              r["ok"] and any(x["order_id"] == oid and x["operator_name"] == "Ali" for x in r["chats"]), r)
        r = await (await cli.get("/api/messages", params={**A_OTHER, "order_id": oid,
                                                           "shared": 1})).json()
        check("umumiy bo'limdan boshqa operator yozishmasi ko'rinadi",
              r["ok"] and r["operator_name"] == "Ali", r)
        await cli.get("/api/messages", params={**A_OTHER, "order_id": oid,
                                                "shared": 1, "mark": 1})
        await q.add_message(oid, "client", "text", "birinchi yangi", None, 14)
        await q.add_message(oid, "client", "text", "ikkinchi yangi", None, 15)
        r = await (await cli.get("/api/general_chats", params=A_OTHER)).json()
        gc = next(x for x in r["chats"] if x["order_id"] == oid)
        check("umumiy chatda 2 ta yangi xabar badge'i 2 bo'ladi", gc["unread"] == 2, gc)
        r = await (await cli.get("/api/general_clients", params=A_OTHER)).json()
        check("umumiy mijozlarda barcha operatorlar mijozlari ko'rinadi",
              r["ok"] and any(x["tg"] == 5001 and x["operator_name"] == "Ali"
                              for x in r["clients"]), r)
        r = await (await cli.post("/api/typing", json={**A_OTHER, "order_id": oid,
                                                        "shared": 1})).json()
        rs = await (await cli.get("/api/sync", params={**A, "v": 0, "order_id": oid})).json()
        check("umumiy chatda boshqa operator yozayotgani ko'rinadi",
              r["ok"] and "Vali" in rs.get("typing", []), rs.get("typing"))
        peers = await (await cli.get("/api/operator_peers", params=A)).json()
        vali = next(x for x in peers["operators"] if x["id"] == op2)
        check("operator faolligi va ochib turgan chati ko'rinadi",
              vali["online"] and vali["viewing_order_id"] == oid and vali["viewing_client"], vali)
        resp = await cli.post("/api/order_tags", json={**A_OTHER, "order_id": oid, "tags": ["Begona"]})
        check("boshqa operator tegni o'zgartira olmaydi", resp.status == 403, resp.status)

        print("CHAT STATE / TAGS / NOTES / PIN")
        r = await (await cli.post("/api/chat_state", json={**A, "order_id": oid, "pinned": True, "draft": "<b>qoralama</b>"})).json()
        r2 = await (await cli.get("/api/chats", params=A)).json()
        c = r2["chats"][0]
        check("qadash + qoralama saqlandi", c["pinned"] and c["draft"] == "<b>qoralama</b>", c)
        r = await (await cli.post("/api/order_tags", json={**A, "order_id": oid, "tags": ["Narx so'rovi", "Retsept"]})).json()
        check("teglar", r["ok"] and r["tags"] == ["Narx so'rovi", "Retsept"], r)
        r = await (await cli.post("/api/inote", json={**A, "order_id": oid, "text": "ichki"})).json()
        check("ichki izoh", r["ok"])
        r = await (await cli.post("/api/pin", json={**A, "order_id": oid, "mid": m1})).json()
        r2 = await (await cli.get("/api/messages", params={**A, "order_id": oid})).json()
        check("qadalgan xabar + izoh + teg metada", r2["pinned"]["mid"] == m1 and r2["notes"][0]["text"] == "ichki" and r2["tags"], r2.get("pinned"))
        r = await (await cli.get("/api/tags", params=A)).json()
        check("teg presetlari", r["ok"] and "Retsept" in r["tags"], r)

        print("SHABLONLAR")
        r = await (await cli.post("/api/tpl_add", json={**A, "text": "Salom {ism}!"})).json()
        tid = r["id"]
        r = await (await cli.get("/api/templates", params=A)).json()
        check("shaxsiy shablon ro'yxatda", any(t["id"] == tid and t["own"] for t in r["items"]), r)
        r = await (await cli.post("/api/tpl_del", json={**A, "id": 1})).json()
        check("umumiy shablonni operator o'chira olmaydi", not r["ok"])
        r = await (await cli.post("/api/tpl_del", json={**A, "id": tid})).json()
        check("o'z shablonini o'chiradi", r["ok"])
        order = await q.get_order(oid)
        plain, html = await webapp._prepare_text({"html": "Salom <b>{ism}</b>"}, order, op)
        check("shablon o'zgaruvchisi + format", html == "Salom <b>Ra&#x27;no O&#x27;g&#x27;iloy</b>" or html == "Salom <b>Ra'no O'g'iloy</b>", html)
        plain, html = await webapp._prepare_text({"text": "<b> Ozodbek <b> salom"}, order, op)
        check("qo'lda yozilgan <b> Ozodbek <b>", html == "<b> Ozodbek </b> salom" and plain == "Ozodbek  salom".replace("  ", "  "), (plain, html))

        print("SEND (bot yo'q)")
        r = await (await cli.post("/api/send", json={**A, "order_id": oid, "text": "x"})).json()
        check("bot yo'q bo'lsa tushunarli xato", not r["ok"] and "bot" in r["error"], r)

        print("SEND / REPLY / MEDIA / EDIT")
        import utils
        class ChatBot:
            def __init__(self): self.mid = 200; self.calls = []
            def _sent(self, **kw):
                self.mid += 1
                return SimpleNamespace(message_id=self.mid, **kw)
            async def send_message(self, *args, **kwargs):
                self.calls.append(("text", args, kwargs)); return self._sent()
            async def send_photo(self, *args, **kwargs):
                self.calls.append(("photo", args, kwargs)); return self._sent(photo=[SimpleNamespace(file_id="photo-fid")])
            async def send_document(self, *args, **kwargs):
                self.calls.append(("document", args, kwargs)); return self._sent(document=SimpleNamespace(file_id="doc-fid", mime_type="text/plain"))
            async def send_voice(self, *args, **kwargs):
                self.calls.append(("voice", args, kwargs)); return self._sent(voice=SimpleNamespace(file_id="voice-fid"))
            async def send_audio(self, *args, **kwargs):
                return self._sent(audio=SimpleNamespace(file_id="audio-fid"))
            async def send_sticker(self, *args, **kwargs):
                self.calls.append(("sticker", args, kwargs)); return self._sent()
            async def delete_message(self, *args, **kwargs):
                self.calls.append(("delete", args, kwargs)); return True
            async def edit_message_text(self, *args, **kwargs):
                self.calls.append(("edit", args, kwargs)); return True
        chat_bot = ChatBot()
        utils.cbot = lambda: chat_bot
        r = await (await cli.post("/api/send", json={**A, "order_id": oid, "text": "javob",
                                                       "reply_mid": m1})).json()
        sent_mid = r.get("mid")
        check("reply bilan matn yuborish", r["ok"] and chat_bot.calls[-1][2].get("reply_to_message_id") == 10, r)
        r = await (await cli.post("/api/send", json={**A_OTHER, "order_id": oid, "shared": 1,
                                                       "text": "umumiydan yordam"})).json()
        shared_call = chat_bot.calls[-1]
        check("umumiydan javob chat egasi nomidan yuboriladi",
              r["ok"] and "Ali" in shared_call[1][1] and "Vali" not in shared_call[1][1]
              and (await q.get_order(oid))["operator_id"] == op_id, (r, shared_call))
        help_oid = await q.create_order(5001, None, "text")
        await q.claim_order(help_oid, op_id)
        r = await (await cli.post("/api/order_tags", json={**A_OTHER, "order_id": help_oid,
                                                             "shared": 1, "tags": ["Yordam"]})).json()
        check("umumiy chatda teg tugmasi ishlaydi", r["ok"] and "Yordam" in r["tags"], r)
        r = await (await cli.post("/api/pause", json={**A_OTHER, "order_id": help_oid,
                                                        "shared": 1, "reason": "Tekshiruv",
                                                        "minutes": 60})).json()
        check("umumiy chatda pauza tugmasi ishlaydi",
              r["ok"] and (await q.get_order(help_oid))["paused_at"], r)
        gp = await (await cli.get("/api/general_chats",
                                  params={**A_OTHER, "kind": "paused"})).json()
        check("umumiy Pauzada papkasi", any(x["order_id"] == help_oid for x in gp["chats"]), gp)
        r = await (await cli.post("/api/close", json={**A_OTHER, "order_id": help_oid,
                                                        "shared": 1})).json()
        help_order = await q.get_order(help_oid)
        check("umumiy chatda yakunlash tugmasi ishlaydi va egasi o'zgarmaydi",
              r["ok"] and help_order["status"] == "done" and help_order["operator_id"] == op_id,
              (r, dict(help_order)))
        gd = await (await cli.get("/api/general_chats",
                                  params={**A_OTHER, "kind": "done"})).json()
        check("umumiy Yakunlangan papkasi",
              any(x["order_id"] == help_oid and x["operator_name"] == "Ali" for x in gd["chats"]), gd)
        gh = await (await cli.get("/api/messages", params={**A_OTHER, "order_id": help_oid,
                                                            "shared": 1})).json()
        check("umumiy yakunlangan chat yozishmasi ochiladi", gh["ok"], gh)
        r = await (await cli.post("/api/msg_edit", json={**A, "mid": sent_mid, "text": "tahrirlangan"})).json()
        check("yuborilgan xabarni tahrirlash", r["ok"] and (await q.get_message(sent_mid))["text"] == "tahrirlangan", r)
        raw64 = base64.b64encode(b"test-media").decode()
        r = await (await cli.post("/api/send", json={**A, "order_id": oid, "media_kind": "photo",
                                                       "media_data": raw64, "text": "rasm"})).json()
        photo_mid = r.get("mid") or r.get("message", {}).get("mid")
        check("rasm yuborish", r["ok"] and r["message"]["type"] == "photo", r)
        r = await (await cli.post("/api/send", json={**A, "order_id": oid, "media_kind": "document",
                                                       "media_data": raw64, "media_name": "test.txt"})).json()
        doc_mid = r.get("mid") or r.get("message", {}).get("mid")
        check("fayl yuborish", r["ok"] and r["message"]["type"] == "document", r)
        r = await (await cli.post("/api/send", json={**A, "order_id": oid, "media_kind": "voice",
                                                       "media_data": raw64, "media_mime": "audio/ogg"})).json()
        check("ovoz yuborish", r["ok"] and r["message"]["type"] == "voice", r)
        sticker_id = await q.add_template(None, "sticker-fid")
        r = await (await cli.post("/api/send_sticker", json={**A, "order_id": oid,
                                                              "sticker_id": sticker_id})).json()
        check("sticker yuborish", r["ok"] and any(c[0] == "sticker" for c in chat_bot.calls), r)
        r = await (await cli.post("/api/msg_delete_many", json={**A, "mids": [photo_mid, doc_mid, m1]})).json()
        check("tanlangan rasm va faylni ommaviy o'chirish", r["ok"] and len(r["deleted"]) == 2 and m1 in r["skipped"], r)

        r = await (await cli.post("/api/cmd", json={**A, "order_id": oid, "cmd": "autoclose"})).json()
        check("10 daqiqalik taymer bazada saqlandi", r["ok"] and (await q.get_order(oid))["auto_close_at"], r)
        await q.add_message(oid, "client", "text", "taymerni bekor qiluvchi javob", None, 13)
        check("mijoz javobida taymer bekor qilindi", (await q.get_order(oid))["auto_close_at"] is None)
        utils.cbot = lambda: None

        print("TRANSFER / OPS")
        r = await (await cli.get("/api/ops_list", params=A)).json()
        check("operatorlar ro'yxati", r["ok"] and r["items"][0]["name"] == "Vali", r)
        transfer_oid = await q.create_order(5001, None, "text")
        await q.claim_order(transfer_oid, op_id)
        r = await (await cli.post("/api/transfer", json={**A, "order_id": transfer_oid,
                                                          "to_id": op2, "note": "Valiga"})).json()
        check("operatorga o'tkazish", r["ok"] and (await q.get_order(transfer_oid))["operator_id"] == op2, r)
        resp = await cli.post("/api/inote", json={**A, "order_id": transfer_oid, "text": "eski operator"})
        check("o'tkazilgach eski operator o'zgartira olmaydi", resp.status == 403, resp.status)
        r = await (await cli.post("/api/transfer", json={**A_OTHER, "order_id": transfer_oid,
                                                          "to_id": op_id, "note": "qaytarildi"})).json()
        check("murojaatni qayta o'tkazish", r["ok"] and (await q.get_order(transfer_oid))["operator_id"] == op_id, r)

        print("OPERATORLARARO ICHKI CHAT / BILDIRISHNOMA")
        r = await (await cli.get("/api/operator_peers", params=A)).json()
        check("boshqa operator chatlar ro'yxatida", r["ok"] and any(x["id"] == op2 for x in r["operators"]), r)
        r = await (await cli.post("/api/operator_send", json={**A, "peer_id": op2, "text": "Vali, yordam kerak"})).json()
        check("operatorga ichki xabar yuborildi", r["ok"], r)
        r = await (await cli.get("/api/operator_messages", params={**A_OTHER, "peer_id": op_id})).json()
        check("ikkinchi operator xabarni ko'radi", r["ok"] and r["messages"][-1]["text"] == "Vali, yordam kerak" and not r["messages"][-1]["own"], r)
        r = await (await cli.get("/api/notifications", params=A_OTHER)).json()
        check("ichki xabar mini-app bildirishnomasiga keldi", any(x["kind"] == "operator_message" for x in r["items"]), r)
        await cli.post("/api/notifications/read", json=A_OTHER)
        check("bildirishnomalar o'qilgan deb belgilandi", await q.operator_notifications_unread(op2) == 0)

        from handlers.order import _notify_operators_rating
        await q.set_order_rating(oid, 5)
        await _notify_operators_rating(chat_bot, oid, None, None)
        notes = await q.operator_notifications(op_id)
        check("None/5 o'rniga bazadagi haqiqiy baho", any("5/5" in n["title"] for n in notes), [n["title"] for n in notes])

        print("FILE / MEDIA KEY")
        r = await cli.get("/api/file", params={"fid": "x", "kind": "photo", "mk": "bad"})
        check("noto'g'ri media kaliti 401", r.status == 401)
        r = await cli.get("/api/file", params={"fid": "x", "kind": "photo", "mk": mk})
        check("to'g'ri media kaliti o'tadi (bot yo'q -> 503)", r.status == 503, r.status)

        print("WALLPAPER")
        r = await (await cli.post("/api/wallpaper", json={**A, "preset": "ocean", "dim": 20})).json()
        check("fon saqlandi", r["ok"] and r["preset"] == "ocean" and r["dim"] == 20, r)
        r = await (await cli.get("/api/wallpaper", params=A)).json()
        check("fon o'qildi", r["preset"] == "ocean", r)

        print("DELETE AUDIT + CLOSE")
        mo = await q.add_message(oid, "operator", "text", "o'chiriladigan", None, None, client_msg_id=99)
        r = await (await cli.post("/api/msg_del", json={**A, "mid": mo})).json()
        check("xabar o'chirildi (bot yo'q)", r["ok"], r)
        dels = await q.deleted_messages(oid)
        check("o'chirilgan asl matn auditda", any("o'chiriladigan" in d["details"] for d in dels), dels)

        print("ADMIN")
        atok = await webapp._admin_sign(111)
        AA = {"admin_id": 111, "token": atok}
        r = await (await cli.get("/api/admin/msgs", params={**AA, "order_id": oid})).json()
        kinds = [m.get("kind") for m in r["messages"]]
        check("admin yozishmada izoh va o'chirilgan xabar", "note" in kinds and "deleted" in kinds, kinds)
        r = await (await cli.get("/api/admin/audit", params=AA)).json()
        check("audit jurnali", r["ok"] and r["total"] > 0 and any(i["action"] == "msg_delete" for i in r["items"]), r.get("total"))
        r = await (await cli.get("/api/admin/sla", params={**AA, "period": "year"})).json()
        check("SLA hisobot", r["ok"] and r["items"], r)
        r = await (await cli.get("/api/admin/orders", params={**AA, "tag": "Retsept"})).json()
        check("teg bo'yicha filtr", r["ok"] and r["total"] == 1 and r["items"][0]["tags"], r)
        r = await (await cli.get("/api/admin/dash", params={**AA, "period": "month"})).json()
        check("dash teglar", r["ok"] and r["tags"], r.get("tags"))
        r = await (await cli.post("/api/admin/settings_save", json={**AA, "auto_assign": "least"})).json()
        check("auto_assign saqlandi", r["ok"] and await q.get_setting("auto_assign") == "least")
        # viewer roli
        await q.add_admin(222, "sup", "Sup", added_by=111)
        r = await (await cli.post("/api/admin/admin_role", json={**AA, "telegram_id": 222, "role": "viewer"})).json()
        check("rol o'zgardi", r["ok"], r)
        VT = {"admin_id": 222, "token": await webapp._admin_sign(222)}
        r = await cli.get("/api/admin/orders", params=VT)
        check("viewer ko'ra oladi", r.status == 200)
        r = await cli.post("/api/admin/close", json={**VT, "order_id": oid})
        check("viewer o'zgartira olmaydi (403)", r.status == 403, r.status)
        r = await (await cli.post("/api/admin/inote", json={**AA, "order_id": oid, "text": "admin izohi"})).json()
        check("admin ichki izoh", r["ok"], r)
        # sessiyalarni bekor qilish
        r = await (await cli.post("/api/admin/revoke_sessions", json=AA)).json()
        r2 = await cli.get("/api/admin/orders", params=AA)
        check("eski admin tokeni bekor", r2.status == 401, r2.status)
        r3 = await cli.get("/api/admin/orders", params={"admin_id": 111, "token": r["token"]})
        check("yangi admin tokeni ishlaydi", r3.status == 200)
        # operator sessiyasini bekor qilish
        r = await (await cli.post("/api/admin/op_logout", json={"admin_id": 111, "token": r["token"], "id": op_id})).json()
        r2 = await cli.get("/api/chats", params=A)
        check("operator sessiyasi bekor qilindi", r2.status == 401, r2.status)
        await q.set_setting("admin_epoch", "0")

        print("AUTO-ASSIGN")
        oid2 = await q.create_order(5001, None, "text")
        from handlers.operator import try_auto_assign
        import handlers.operator as operator_mod
        import utils
        utils.cbot = lambda: None
        operator_mod.cbot = lambda: None
        ok = await try_auto_assign(oid2)
        check("bot yo'q bo'lsa avto-taqsimlash xatosiz o'tadi", ok is False)


        print("PAUZA")
        import webapp_extra as webapp_extra_mod
        A2 = {"operator_id": op_id, "token": (await (await cli.post("/api/login", json={"login": "ali", "password": "1234"})).json())["token"]}
        class GuardBot:
            def __init__(self): self.sent = []
            async def send_message(self, *args, **kwargs):
                self.sent.append((args, kwargs))
                return type("Sent", (), {"message_id": 9001})()
        guard_bot = GuardBot()
        utils.cbot = lambda: guard_bot
        r = await (await cli.post("/api/pause", json={**A2, "order_id": oid, "reason": "Mijoz ertaga yozadi", "minutes": 600, "tell_client": True})).json()
        check("pauzaga qo'yildi", r["ok"], r)
        check("pauza mijozga xabar yubormaydi", len(guard_bot.sent) == 0, guard_bot.sent)
        utils.cbot = lambda: None
        r = await (await cli.get("/api/chats", params=A2)).json()
        check("ro'yxatda pauza belgisi", r["chats"][0]["paused"], r["chats"][0])
        db = await q.get_db()
        await db.execute("UPDATE orders SET paused_at='2026-01-01 10:00:00' WHERE id=?", (oid,))
        await db.commit()
        await q.add_message(oid, "client", "text", "salom, qaytdim", None, 50)
        o = await q.get_order(oid)
        check("mijoz yozsa pauza tugaydi, vaqt hisoblanadi", o["paused_at"] is None and (o["paused_total_min"] or 0) > 1000, dict(o))
        r = await (await cli.get("/api/messages", params={**A2, "order_id": oid})).json()
        check("pauza tarixi yozishmada", r["pause"]["history"] and r["pause"]["history"][0]["by"] == "client", r.get("pause"))
        rows = await q.sla_rows("2000-01-01 00:00:00")
        check("SLA qatorida pauza daqiqalari", any((x["paused_total_min"] or 0) > 0 for x in rows))
        await q.pause_order(oid, op_id, "Dori kutilmoqda", None)
        r = await (await cli.post("/api/pause", json={**A2, "order_id": oid, "resume": 1})).json()
        o = await q.get_order(oid)
        check("operator davom ettira oladi", r["ok"] and o["paused_at"] is None, r)

        print("PAUZA ESLATMASI (faqat ish vaqtida)")
        r = await (await cli.post("/api/pause", json={**A2, "order_id": oid, "reason": "Dori kutilmoqda", "remind": 30})).json()
        o = await q.get_order(oid)
        check("eslatma oralig'i saqlandi", r["ok"] and o["pause_remind_min"] == 30 and o["pause_next_remind"], dict(o))
        await db.execute("UPDATE orders SET pause_next_remind='2000-01-01 00:00:00' WHERE id=?", (oid,))
        await db.execute("UPDATE operators SET telegram_id=555, work_start='00:00', work_end='00:01' WHERE id=?", (op_id,))
        await db.commit()
        due = await q.due_pause_reminders()
        check("eslatma vaqti keldi", any(x["id"] == oid for x in due))
        await webapp_extra_mod._send_pause_reminder([x for x in due if x["id"] == oid][0])
        o = await q.get_order(oid)
        check("ish vaqtidan tashqarida yuborilmaydi (kutadi)", o["pause_next_remind"] == "2000-01-01 00:00:00", o["pause_next_remind"])
        await db.execute("UPDATE operators SET work_start='00:00', work_end='23:59' WHERE id=?", (op_id,))
        await db.commit()
        await webapp_extra_mod._send_pause_reminder((await q.due_pause_reminders())[0])
        o = await q.get_order(oid)
        check("ish vaqtida — keyingi eslatma 30 daqiqaga surildi", o["pause_next_remind"] > q.now(), o["pause_next_remind"])
        await q.resume_order(oid, "operator")
        o = await q.get_order(oid)
        check("davom ettirilganda eslatma o'chadi", o["pause_remind_min"] is None, dict(o))

        print("KATALOG / HISOB-KITOB")
        import webapp_extra
        a, u = await q.import_products([("Парацетамол 500мг", 12000, "quti", "", 1), ("Vitamin D3", 95000, "", "", 0)])
        check("katalog import", a == 2)
        r = await (await cli.get("/api/products", params={**A2, "q": "paracetamol"})).json()
        check("kirill/lotin qidiruv", r["ok"] and r["items"] and r["items"][0]["price"] == 12000, r)
        vit = (await q.search_products("vitamin"))[0]
        r = await (await cli.post("/api/stock_wait", json={**A2, "order_id": oid, "product_id": vit["id"]})).json()
        check("kelganda xabar navbati", r["ok"] and (await q.stock_wait_counts()).get(vit["id"]) == 1, r)
        text, total = webapp_extra.build_bill_text([{"name": "Paratsetamol", "qty": 2, "price": 12000}], 10000, "tez")
        check("hisob-kitob matni", total == 34000 and "34 000" in text and "2 × 12 000" in text, text)
        import openpyxl
        import io as _io
        import base64 as _b64
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Nomi", "Narxi", "Mavjud"])
        ws.append(["Aspirin", "5 000", "bor"])
        ws.append(["Vitamin D3", 95000, 3])
        buf = _io.BytesIO()
        wb.save(buf)
        AT = {"admin_id": 111, "token": await webapp._admin_sign(111)}
        r = await (await cli.post("/api/admin/products_import", json={**AT, "data": _b64.b64encode(buf.getvalue()).decode()})).json()
        check("Excel import (yangilash + yangi)", r["ok"] and r["added"] == 1 and r["updated"] == 1, r)
        check("bot ishlamasa kelgan dori navbati yo'qolmaydi", (await q.stock_wait_counts()).get(vit["id"]) == 1)
        stock_bot = GuardBot()
        utils.cbot = lambda: stock_bot
        sent = await webapp_extra.notify_stock_arrived(vit["id"])
        check("xabar yuborilgach dori navbatdan chiqdi", sent == 1 and not (await q.stock_wait_counts()).get(vit["id"]))
        utils.cbot = lambda: None

        print("HISOBOT / MAQSAD")
        t = await webapp_extra.daily_report_text()
        check("kunlik hisobot matni", "Kunlik hisobot" in t and "Murojaatlar" in t, t[:80])
        await q.set_setting("op_daily_goal", "5")
        r = await (await cli.get("/api/profile", params=A2)).json()
        check("profilda kunlik maqsad", r["goal"]["goal"] == 5, r.get("goal"))

        print("O'CHIRISH (filial kartasi)")
        mb = await q.add_message(oid, "operator", "text", "📋 <b>Filial</b>", None, None, client_msg_id=7, extra_cmids=[8, 9])
        row = await q.get_message(mb)
        check("<b> HTML ga ajratildi", row["html"] == "📋 <b>Filial</b>" and row["text"] == "📋 Filial" and row["extra_cmids"] == "8,9", dict(row))
        r = await (await cli.post("/api/msg_del", json={**A2, "mid": mb})).json()
        check("filial kartasini o'chirish mumkin", r["ok"], r)

        print("BEKOR QILISH / OTKAZ")
        oid3 = await q.create_order(5001, None, "text")
        await q.claim_order(oid3, op_id)
        r = await (await cli.post("/api/reject", json={**A2, "order_id": oid3})).json()
        o = await q.get_order(oid3)
        check("otkaz belgilandi, chat ochiq qoldi", r["ok"] and o["rejected_at"] and o["status"] == "in_progress", dict(o))
        r = await (await cli.get("/api/done_chats", params={**A2, "kind": "rejected"})).json()
        check("Otkaz papkasi", any(c["order_id"] == oid3 for c in r["chats"]), r)
        r = await (await cli.post("/api/cancel", json={**A2, "order_id": oid3})).json()
        o = await q.get_order(oid3)
        check("bekor qilindi", r["ok"] and o["status"] == "canceled", r)
        r = await (await cli.get("/api/done_chats", params={**A2, "kind": "canceled"})).json()
        check("Bekor qilingan papkasi", any(c["order_id"] == oid3 for c in r["chats"]), r)
        r = await (await cli.get("/api/general_chats",
                                 params={**A_OTHER, "kind": "canceled"})).json()
        check("umumiy Bekor qilingan papkasi", any(c["order_id"] == oid3 for c in r["chats"]), r)
        r = await (await cli.get("/api/done_chats", params={**A2, "kind": "done"})).json()
        check("Yakunlangan papkasida bekor qilingan yo'q", all(c["status"] == "done" for c in r["chats"]), r)

        print("STATIC")
        r = await cli.get("/fmt.js")
        check("/fmt.js beriladi", r.status == 200 and "TGF" in await r.text())
        r = await cli.get("/static/gulnora-farm-logo.jpg")
        check("Gulnora Farm logosi beriladi", r.status == 200 and r.content_type == "image/jpeg" and len(await r.read()) > 1000)
    finally:
        await cli.close()
    print(f"\nNATIJA: {OK} o'tdi, {FAIL} xato")
    sys.exit(1 if FAIL else 0)

asyncio.run(main())
