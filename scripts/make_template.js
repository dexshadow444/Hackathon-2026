// Generates app/assets/idea-presentation-template.pptx (green / light-blue / white theme)
// Run: node scripts/make_template.js
const pptxgen = require("pptxgenjs");
const path = require("path");

const G = "147A47", GD = "0F6B3F", GT = "E6F6EC", B = "5BB8E8", BP = "E3F3FC", T = "12312B", M = "4B6360";
const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5 in
pres.title = "Hackathon Idea Presentation Template";
pres.theme = { headFontFace: "Calibri", bodyFontFace: "Calibri" };

// ---- Title slide ----
let s = pres.addSlide();
s.background = { color: "FFFFFF" };
s.addShape(pres.ShapeType.rect, { x: 0, y: 0, w: 13.33, h: 7.5, fill: { color: BP }, line: { color: BP } });
s.addShape(pres.ShapeType.rect, { x: 0, y: 0, w: 0.35, h: 7.5, fill: { color: G }, line: { color: G } });
s.addShape(pres.ShapeType.rect, { x: 0.35, y: 0, w: 0.12, h: 7.5, fill: { color: B }, line: { color: B } });
s.addText("Your idea title goes here", { x: 1.1, y: 2.0, w: 11, h: 1.3, fontSize: 44, bold: true, color: GD, isTextBox: true, margin: 0 });
s.addText("One line that explains what it does and who it helps", { x: 1.1, y: 3.4, w: 11, h: 0.6, fontSize: 22, color: M, isTextBox: true, margin: 0 });
s.addShape(pres.ShapeType.rect, { x: 1.1, y: 4.45, w: 1.4, h: 0.06, fill: { color: G }, line: { color: G } });
s.addText([
  { text: "Team name: ", options: { bold: true, color: GD } }, { text: "your team name", options: { color: T, breakLine: true } },
  { text: "College: ", options: { bold: true, color: GD } }, { text: "your college or institution", options: { color: T, breakLine: true } },
  { text: "Track: ", options: { bold: true, color: GD } }, { text: "the track you chose", options: { color: T } },
], { x: 1.1, y: 4.75, w: 11, h: 1.5, fontSize: 18, isTextBox: true, margin: 0, paraSpaceAfter: 6 });

// ---- Content slides ----
const slides = [
  ["Track focus and proposed solution", [
    "Which track does your idea belong to, and why?",
    "What problem are you solving, and who faces it?",
    "Describe your solution in two or three sentences.",
  ]],
  ["Technical architecture", [
    "Show the main components and how data flows between them.",
    "List the tech stack: frontend, backend, database, any APIs.",
    "What can your team realistically build as a 24-hour prototype?",
  ]],
  ["Feasibility, viability and novelty", [
    "Feasibility: can it be built with the skills and tools you have?",
    "Viability: who would use it, and how could it be sustained?",
    "Novelty: how is it different from what already exists?",
  ]],
  ["Societal impact", [
    "Who benefits, and how many people could it reach?",
    "What measurable change do you expect?",
    "Any risks or ethical points the team has considered?",
  ]],
];

slides.forEach(([title, prompts], i) => {
  const sl = pres.addSlide();
  sl.background = { color: "FFFFFF" };
  sl.addShape(pres.ShapeType.rect, { x: 0, y: 0, w: 13.33, h: 1.25, fill: { color: BP }, line: { color: BP } });
  sl.addShape(pres.ShapeType.rect, { x: 0, y: 0, w: 0.3, h: 1.25, fill: { color: G }, line: { color: G } });
  sl.addText(title, { x: 0.8, y: 0.25, w: 11.7, h: 0.75, fontSize: 30, bold: true, color: GD, isTextBox: true, margin: 0, valign: "middle" });

  sl.addShape(pres.ShapeType.roundRect, { x: 0.8, y: 1.7, w: 11.73, h: 4.6, fill: { color: "FFFFFF" }, line: { color: "CFE5EC", width: 1.25 }, rectRadius: 0.12 });
  sl.addText("Replace the prompts below with your content", { x: 1.1, y: 1.9, w: 11, h: 0.4, fontSize: 14, italic: true, color: M, isTextBox: true, margin: 0 });
  sl.addText(prompts.map((p, k) => ({ text: p, options: { bullet: true, breakLine: k < prompts.length - 1 } })), {
    x: 1.1, y: 2.5, w: 11.1, h: 3.5, fontSize: 20, color: T, isTextBox: true, margin: 0, valign: "top", paraSpaceAfter: 14,
  });

  sl.addText("Team name  |  Idea title", { x: 0.8, y: 6.75, w: 8, h: 0.35, fontSize: 12, color: M, isTextBox: true, margin: 0 });
  sl.addText(`${i + 2}`, { x: 11.9, y: 6.75, w: 0.63, h: 0.35, fontSize: 12, color: M, align: "right", isTextBox: true, margin: 0 });
});

pres.writeFile({ fileName: path.join(__dirname, "..", "app", "assets", "idea-presentation-template.pptx") })
  .then((f) => console.log("wrote", f));
