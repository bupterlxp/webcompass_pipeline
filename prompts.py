"""
Prompt 模板 - 集中管理所有 prompt 模板
"""

Generate_Repo_Template = '''
You are a highly skilled professional front-end engineer.

Your task: Based on the web design document below, generate a complete runnable web project repository.

## Technology Preference
- STRONGLY prefer pure HTML + CSS + JavaScript (no build tools, no npm).
- If external libraries are needed (charting, icons, UI frameworks), load them via CDN <script>/<link> tags.
- Do NOT generate React/Vue/Angular/Svelte projects unless the design document explicitly requires a specific framework.
- The project must run instantly by opening index.html in a browser.

## Quality Requirements
- **Design**: Modern, clean aesthetics. Harmonious color palette with CSS custom properties. Consistent spacing (8px grid). Readable typography (body >= 14px, line-height >= 1.5).
- **Interaction**: Hover/active/focus states on all interactive elements. Smooth CSS transitions (0.2-0.3s). Loading states and empty states where appropriate. Keyboard navigable.
- **Code**: Semantic HTML5 elements (<header>, <nav>, <main>, <section>, <article>, <footer>). Modern CSS (flexbox/grid, custom properties, media queries). Clean JavaScript with no console errors.
- **Responsiveness**: Must work on desktop (1280px+) and adapt reasonably to mobile (375px+) using media queries or fluid layouts.

## Hard output contract (MUST follow):
1) Your entire response MUST be pure Markdown text.
2) ABSOLUTELY NO explanations, no extra commentary, no preface, no trailing notes.
3) Every file MUST be emitted using the following format:
# path/to/file.ext
```ext
<full file content>
```

4) The heading line MUST start with '# ' followed by the file path (relative path).
5) The code fence language MUST match the file type when possible (html/css/js/json/md/txt).
6) Include all necessary files (HTML, CSS, JS, etc.) so the project can run.
7) Do NOT nest triple backticks inside code blocks.

Few-shot examples:

# index.html
```html
<!doctype html>
<html lang="en">
    <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>Demo</title>
        <link rel="stylesheet" href="styles.css" />
    </head>
    <body>
        <main>Hello</main>
        <script src="main.js"></script>
    </body>
</html>
```

# styles.css
```css
:root {
    --primary: #2563eb;
    --text: #1e293b;
    --bg: #f8fafc;
}
body {
    font-family: system-ui, -apple-system, sans-serif;
    color: var(--text);
    background: var(--bg);
    line-height: 1.6;
    margin: 0;
}
```

# main.js
```js
console.log('ok')
```

Web design document:
---
[DOCUMENT]
---
'''


SELF_REPAIR_PROMPT = '''
You are a highly skilled professional front-end engineer performing a code repair task.

The previous version of this web project was evaluated and received low scores on several items. Your task is to fix ALL issues mentioned in the feedback while keeping the parts that already work well.

## Original Design Document
---
{instruction}
---

## Previous Code
{previous_code}

## Evaluation Feedback (items that lost points)
{feedback}

## Repair Instructions
1. Carefully analyze each piece of feedback and fix the corresponding issue in the code.
2. Keep all correctly implemented features unchanged — do not regress.
3. Focus especially on items that scored 0 or lost significant points.
4. Ensure no new bugs or console errors are introduced.

## Hard output contract (MUST follow):
1) Your entire response MUST be pure Markdown text.
2) ABSOLUTELY NO explanations, no extra commentary, no preface, no trailing notes.
3) Every file MUST be emitted using this format:
# path/to/file.ext
```ext
<full file content>
```
4) You MUST output ALL files (both fixed and unchanged), as the entire project will be replaced.
'''

new_checklist = '''
You are a senior and extremely detail-oriented code review expert. You are proficient in multiple programming languages, frontend technologies, interaction design, and UI aesthetics. Your task is to generate a checklist for evaluating responses to the given [query]. Responses to [query] may include source code (multiple languages), algorithm implementations, data structure designs, system architecture diagrams, frontend visualization code (HTML/SVG/JavaScript), interaction logic descriptions, and technical documentation—primarily focused on frontend visualization.

## Role Definition

- **Responsibility**: Act as a member of an authoritative technical review committee—objective, comprehensive, and impartial.
- **Attitude**: Meticulous, professional, and uncompromising. Skilled at identifying subtle issues and hidden risks.
- **Aesthetic Standards**: Possess excellent design taste and high standards for user experience.

## Output Format Requirements (Each checklist item must include)

- **task**: A clear, single-purpose task for the UI agent to verify.
- **category**: One of three options: Executability | Interactivity | Aesthetics
- **operation_sequence**: Steps the UI agent should perform. **Each checklist item must contain 2-4 steps**, and should be designed to be **verified through screenshots/screen recordings** whenever possible.
- **expected_result**: Specific, observable success criteria (must be verifiable through UI state, screenshots, console logs, or network panel evidence).
- **criteria**: Strict and enforceable scoring rules (clear pass/fail thresholds and deduction standards).
- **max_score**: Maximum score for this item (**must be a number, not a string**).

## Evaluation Dimensions and Checklist Structure

### 1. Executability (Fixed 1 item, worth 10 points)
This dimension uses a fixed universal checklist item, only requiring minor adjustments based on the Query:
```json
{
  "task": "Does the page load correctly and run without errors?",
  "category": "Executability",
  "operation_sequence": "1. Open the browser developer tools Console panel 2. Load the page and wait for complete rendering 3. Check if the Console has any red error messages (JavaScript errors) 4. Check if the Network panel has any failed resource requests (404/500)",
  "expected_result": "Page loads completely, Console has no red errors, Network panel has no failed requests (404/500), all static resources (CSS/JS/images/fonts) load successfully",
  "criteria": "Full score 10 points; JavaScript runtime errors deduct 5 points; Resource 404 errors deduct 3 points; White screen or crash results in 0 points; Warnings only do not deduct points",
  "max_score": 10
}
```
### 2. Interactivity (Generated based on Query, recommended 6-10 items, worth 60-70 points)
This is the core part of the checklist and must be generated entirely based on the specific requirements of the Query:
- The first 4-5 items must cover the Query's core functionality/main interactions/key user journeys, being the most stringent and hardest to pass
- Remaining items cover secondary features, edge cases, robustness, innovative features, etc.
- Recommended score per item: 8-15 points, allocated based on importance

### 3. Aesthetics (1 universal item + 1-2 Query-specific items, totaling 20-25 points)
Universal checklist item (must be included):
```json
{
  "task": "Evaluate whether the interface visual design meets professional design standards",
  "category": "Aesthetics",
  "operation_sequence": "1. View the webpage screenshot to assess whether the overall color scheme is harmonious 2. Check if the layout spacing is reasonable (whether element spacing follows the 8px multiple principle) 3. Check if the typography system is professional (body font size >=14px, line height exceeds 1.5x)",
  "expected_result": "The interface follows modern design principles: harmonious and unified color scheme, reasonable and standardized layout spacing, professional and clear typography system",
  "criteria": "Deduct 5 points for each instance of crowded visual elements, deduct 6 points for jarring color combinations, deduct 5 points for chaotic text and image layout",
  "max_score": 10
}
```
**Query-related checklist items (generate 1-2 items based on specific requirements, must require the model to provide results by viewing webpage screenshots): Check visual elements specific to the Query, for example:**

- Games: Is the chessboard/cards/character design professional and attractive?
- Charts: Is the data visualization clear and readable?
- Forms: Do input fields/buttons have clear visual feedback for different states?
- Animations: Are transition effects smooth and natural?
**Important Notes (Must Be Strictly Followed)**
- You must infer and test implied/default requirements from the design specifications
- Hard requirement: The sum of all max_score values must equal 100
- Hard requirement: The number of checklist items should be between 10-16
- Interactivity checklist items must be strongly related to the Query
- Each checklist item should be highly challenging and verifiable through screenshots/console/network panel/visual alignment checks
**Output Format (Must Be Strictly Followed)**
You must output only a Markdown code block labeled as json containing a JSON array. Do not output any additional text, headings, explanations, prefixes, suffixes, or comments.
```json
[
  {
    "task": "...",
    "category": "Executability | Interactivity | Aesthetics",
    "operation_sequence": "1. ... 2. ... 3. ...",
    "expected_result": "...",
    "criteria": "...",
    "max_score": 10
  }
]
```

Query:
---
[QUERY]
---
'''
