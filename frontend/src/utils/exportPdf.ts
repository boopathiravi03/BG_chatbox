import type { Message } from "../types";

export async function exportChatPDF(messages: Message[]) {
  const { jsPDF } = await import("jspdf");
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

export async function exportDocumentPDF(
  title: string,
  content: string,
  filename: string = "BG_AI_Report.pdf",
) {
  const { jsPDF } = await import("jspdf");
  const doc = new jsPDF();

  let y = 20;
  doc.setFontSize(16);
  doc.setFont("helvetica", "bold");
  doc.text(title, 20, y);

  y += 10;
  doc.setFontSize(9);
  doc.setFont("helvetica", "normal");
  doc.text(`Generated: ${new Date().toLocaleString()}`, 20, y);

  y += 12;
  doc.setFontSize(10);
  const lines = doc.splitTextToSize(content || "", 170);

  lines.forEach((line: string) => {
    if (y > 270) {
      doc.addPage();
      y = 20;
    }
    doc.text(line, 20, y);
    y += 5.5;
  });

  doc.save(filename);
}
