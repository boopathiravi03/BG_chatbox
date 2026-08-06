import { jsPDF } from "jspdf";
import type { Message } from "../types";

export function exportChatPDF(messages: Message[]) {
  const doc = new jsPDF();

  let y = 20;

  doc.setFontSize(18);
  doc.text("BG AI Chat Report", 20, y);

  y += 12;

  doc.setFontSize(10);
  doc.text(`Generated: ${new Date().toLocaleString()}`, 20, y);

  y += 15;

  messages.forEach((msg) => {
    const role = msg.role === "user" ? "User" : "BG AI";

    doc.setFontSize(12);
    doc.setFont("helvetica", "bold");
    doc.text(role, 20, y);

    y += 7;

    doc.setFont("helvetica", "normal");

    const text = doc.splitTextToSize(msg.content || "", 170);

    doc.text(text, 20, y);

    y += text.length * 7 + 8;

    if (msg.sql) {
      doc.setFont("helvetica", "bold");
      doc.text("Generated SQL", 20, y);
      y += 7;

      doc.setFont("helvetica", "normal");

      const sql = doc.splitTextToSize(msg.sql || "", 170);

      doc.text(sql, 20, y);

      y += sql.length * 7 + 8;
    }

    if (y > 260) {
      doc.addPage();
      y = 20;
    }
  });

  doc.save("BG_AI_Report.pdf");
}
