import re

file_path = "app/services/agent_service.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update get_agent_history to include inferred status
old_history = '''        return [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ]'''

new_history = '''        return [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "status": "blocked" if "Harness Guardrails" in (m.content or "") else ("escalated" if "TIDAK DITEMUKAN" in (m.content or "") or "ESCALATED" in (m.content or "") else "ok"),
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ]'''

if old_history in content:
    content = content.replace(old_history, new_history)
    print("SUCCESS: Updated get_agent_history")
else:
    print("WARNING: old_history not matched")

# 2. Check test_agent update
target_section = '''        # ======================================================================
        # LEVEL 1: WORKING MEMORY & DATABASE PERSISTENCE
        # ======================================================================'''

new_harness_and_memory = '''        # ======================================================================
        # LEVEL 3: AGENT HARNESS - PRE-CHECK GUARDRAIL (SECURITY & ANTI-LEAK)
        # ======================================================================
        sensitive_keywords = [
            "password", "kata sandi", "secret", "api key", "apikey",
            "token rahasia", "kredensial", "credential", "database password",
            "connection string", "drop table", "select * from users", "bypass guardrail"
        ]
        msg_lower = message_trimmed.lower()
        matched_sensitive = [kw for kw in sensitive_keywords if kw in msg_lower]

        if matched_sensitive:
            # Setup working memory conversation
            conv_title = f"test_session_{agent_id}"
            conv_res = await db.execute(
                select(ConversationModel).where(ConversationModel.title == conv_title)
            )
            conversation = conv_res.scalar_one_or_none()
            if not conversation:
                conversation = ConversationModel(user_id=agent_id, title=conv_title)
                db.add(conversation)
                await db.flush()

            # Rekam pesan user
            user_msg_db = MessageModel(
                conversation_id=conversation.id,
                role="user",
                content=message_trimmed
            )
            db.add(user_msg_db)

            blocked_response = (
                "🛡️ **Permintaan Ditolak oleh Sistem Pengaman (Harness Guardrails)**\n\n"
                "Pesan Anda terdeteksi mengandung permintaan terhadap data sensitif, kredensial internal, "
                "atau kata kunci rahasia yang melanggar kebijakan keamanan sistem. "
                "Untuk menjaga privasi dan keamanan data, permintaan ini tidak dapat diproses."
            )
            assistant_msg_db = MessageModel(
                conversation_id=conversation.id,
                role="assistant",
                content=blocked_response
            )
            db.add(assistant_msg_db)
            await db.commit()

            trace_steps = [{
                "step": 1,
                "step_no": 1,
                "title": "Harness Pre-Check: Security Block",
                "type": "harness_guardrail",
                "tool_name": "pre_check_guardrail",
                "params": {"detected_patterns": matched_sensitive, "input_sample": message_trimmed[:60]},
                "result": {"status": "blocked", "action": "BLOCKED_PRE_LLM", "reason": "Sensitive keyword violation"},
                "detail": f"Pesan diblokir oleh Harness Pre-Check sebelum mencapai LLM demi keamanan (terdeteksi: {', '.join(matched_sensitive)})",
                "duration_ms": 1,
                "status": "error"
            }]

            return AgentTestResponse(
                agent_id=db_agent.id,
                agent_name=db_agent.name,
                response=blocked_response,
                status="blocked",
                trace_steps=trace_steps,
                timestamp=datetime.utcnow(),
            )

        # ======================================================================
        # LEVEL 1: WORKING MEMORY & DATABASE PERSISTENCE
        # ======================================================================'''

if target_section in content:
    content = content.replace(target_section, new_harness_and_memory, 1)
    print("SUCCESS: Inserted Pre-Check Guardrails")
else:
    print("WARNING: target_section not matched")

# 3. Post-Check Guardrail replacement around final response
old_post_check = '''        # Bersihkan jawaban akhir dari monolog internal
        response_clean = _clean_reasoning(raw_response)
        if not response_clean:
            response_clean = raw_response.strip() or "Maaf, saya tidak dapat merangkum data saat ini."

        # Simpan pesan balasan asisten ke database
        assistant_msg_db = MessageModel(
            conversation_id=conversation.id,
            role="assistant",
            content=response_clean
        )
        db.add(assistant_msg_db)
        await db.commit()

        return AgentTestResponse(
            agent_id=db_agent.id,
            agent_name=db_agent.name,
            response=response_clean,
            status="ok",
            trace_steps=trace_steps,
            timestamp=datetime.utcnow(),
        )'''

new_post_check = '''        # ======================================================================
        # LEVEL 3: AGENT HARNESS - POST-CHECK & ESCALATION GUARDRAILS
        # ======================================================================
        final_status = "ok"
        escalation_reasons = []

        # 1. Periksa apakah salah satu hasil eksekusi tool mengindikasikan status NOT_FOUND / gagal
        for step in trace_steps:
            res = step.get("result")
            if isinstance(res, dict):
                st = str(res.get("status", "")).lower()
                if "tidak ditemukan" in st or "not_found" in st:
                    escalation_reasons.append(f"Hasil tool '{step.get('tool_name')}' tidak ditemukan dalam database")
                elif st == "error" or res.get("error"):
                    escalation_reasons.append(f"Tool '{step.get('tool_name')}' mengalami kegagalan eksekusi")

        # 2. Periksa apakah pengguna meminta eskalasi ke staf manusia
        human_escalation_keywords = [
            "bicara dengan manusia", "hubungi staf", "eskalasi", "operator",
            "bantuan manusia", "petugas bpjs", "customer service manusia", "hubungkan ke orang"
        ]
        matched_escalate = [kw for kw in human_escalation_keywords if kw in msg_lower]
        if matched_escalate:
            escalation_reasons.append(f"Pengguna meminta eskalasi manual (kata kunci: {', '.join(matched_escalate)})")

        if escalation_reasons:
            final_status = "escalated"
            trace_steps.append({
                "step": len(trace_steps) + 1,
                "step_no": len(trace_steps) + 1,
                "title": "Harness Post-Check: Escalation to Human",
                "type": "harness_escalation",
                "tool_name": "post_check_escalation",
                "params": {"triggers": escalation_reasons},
                "result": {
                    "action": "ESCALATED",
                    "destination": "BPJS Care Center 165 / Human Agent Specialist",
                    "reason": "; ".join(escalation_reasons)
                },
                "detail": f"Kasus dialihkan ke antrean petugas manusia oleh Harness Post-Check: {'; '.join(escalation_reasons)}",
                "duration_ms": 1,
                "status": "ok"
            })

        # Bersihkan jawaban akhir dari monolog internal
        response_clean = _clean_reasoning(raw_response)
        if not response_clean:
            response_clean = raw_response.strip() or "Maaf, saya tidak dapat merangkum data saat ini."

        # Simpan pesan balasan asisten ke database
        assistant_msg_db = MessageModel(
            conversation_id=conversation.id,
            role="assistant",
            content=response_clean
        )
        db.add(assistant_msg_db)
        await db.commit()

        return AgentTestResponse(
            agent_id=db_agent.id,
            agent_name=db_agent.name,
            response=response_clean,
            status=final_status,
            trace_steps=trace_steps,
            timestamp=datetime.utcnow(),
        )'''

if old_post_check in content:
    content = content.replace(old_post_check, new_post_check, 1)
    print("SUCCESS: Inserted Post-Check Guardrails")
else:
    print("WARNING: old_post_check not matched")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File successfully updated!")
