local listings_languages = {
  bash = { listing = "bash", label = "Bash" },
  python = { listing = "Python", label = "Python" },
  r = { listing = "R", label = "R" },
  shell = { listing = "bash", label = "Shell" },
  sh = { listing = "bash", label = "Shell" },
  sql = { listing = "SQL", label = "SQL" },
  url = {
    listing = "ManualURL",
    labels = { ca = "URL", es = "URL", en = "URL" },
  },
  spreadsheet = {
    listing = "ManualSpreadsheet",
    labels = { ca = "Fórmula", es = "Fórmula", en = "Formula" },
  },
  filetree = {
    listing = "ManualFileTree",
    labels = { ca = "Fitxers", es = "Archivos", en = "Files" },
  },
}

local function latex_escape(value)
  local replacements = {
    ["\\"] = "\\textbackslash{}",
    ["{"] = "\\{",
    ["}"] = "\\}",
    ["$"] = "\\$",
    ["&"] = "\\&",
    ["#"] = "\\#",
    ["_"] = "\\_",
    ["%"] = "\\%",
    ["~"] = "\\textasciitilde{}",
    ["^"] = "\\textasciicircum{}",
  }
  local escaped = {}
  for index = 1, #value do
    local character = value:sub(index, index)
    table.insert(escaped, replacements[character] or character)
  end
  return table.concat(escaped)
end

local function language_code(lang)
  local value = lang and pandoc.utils.stringify(lang) or "en"
  return value:lower():match("^[a-z]+") or "en"
end

local function display_label(definition, lang)
  if definition.labels then
    return definition.labels[language_code(lang)] or definition.labels.en
  end
  return definition.label
end

local function transform_code_block(block, lang)
  if not FORMAT:match("latex") then
    return nil
  end

  local language = nil
  for _, class in ipairs(block.classes) do
    if class ~= "numberLines" then
      language = language or class
    end
  end

  if not language then
    language = "text"
  end

  language = language:lower()
  local definition = listings_languages[language]
  if not definition then
    return pandoc.RawBlock(
      "latex",
      "\\begin{manualverbatim}\n" .. block.text .. "\n\\end{manualverbatim}"
    )
  end

  local options = {}
  table.insert(options, "language=" .. definition.listing)
  local first_number = block.attributes.startFrom
  if first_number and first_number:match("^%d+$") then
    table.insert(options, "firstnumber=" .. first_number)
  end
  local optional = #options > 0 and "[" .. table.concat(options, ",") .. "]" or ""
  return pandoc.RawBlock(
    "latex",
    "\\begin{manualcode}" .. optional .. "{" .. latex_escape(display_label(definition, lang)) .. "}\n" ..
      block.text .. "\n\\end{manualcode}"
  )
end

function Pandoc(document)
  return document:walk({
    CodeBlock = function(block)
      return transform_code_block(block, document.meta.lang)
    end,
  })
end
