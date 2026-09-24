local function append_all(destination, values)
  for _, value in ipairs(values) do
    table.insert(destination, value)
  end
end

local function caption_inlines(caption)
  local result = pandoc.Inlines({})
  for index, block in ipairs(caption.long) do
    if index > 1 then
      table.insert(result, pandoc.Space())
    end
    if block.content then
      append_all(result, block.content)
    else
      table.insert(result, pandoc.Str(pandoc.utils.stringify(block)))
    end
  end
  return result
end

local function description_only(inlines)
  local has_source = false
  local description = inlines:walk({
    Span = function(span)
      if span.classes:includes("uw-caption-source") then
        has_source = true
        return {}
      end
    end
  })
  while #description > 0 and (description[#description].t == "Space" or description[#description].t == "SoftBreak") do
    table.remove(description)
  end
  return description, has_source
end

local function figure_caption(figure)
  if not FORMAT:match("latex") or #figure.caption.long == 0 then
    return nil
  end

  local full = caption_inlines(figure.caption)
  local short, has_source = description_only(full)
  local caption = {}
  if has_source then
    table.insert(caption, pandoc.RawInline("latex", "\\caption[{"))
    append_all(caption, short)
    table.insert(caption, pandoc.RawInline("latex", "}]{"))
  else
    table.insert(caption, pandoc.RawInline("latex", "\\caption{"))
  end
  append_all(caption, full)
  table.insert(caption, pandoc.RawInline("latex", "}"))
  if figure.identifier and figure.identifier ~= "" then
    table.insert(caption, pandoc.RawInline("latex", "\\label{" .. figure.identifier .. "}"))
  end

  local blocks = {
    pandoc.RawBlock("latex", "\\begin{figure}[H]\n\\centering"),
    pandoc.Plain(caption),
  }
  append_all(blocks, figure.content)
  table.insert(blocks, pandoc.RawBlock("latex", "\\end{figure}"))
  return blocks
end

local function table_caption(element)
  if not FORMAT:match("latex") then
    return nil
  end
  local short, has_source = description_only(caption_inlines(element.caption))
  if has_source then
    element.caption.short = short
    return element
  end
end

local function source_style(span)
  if FORMAT:match("latex") and span.classes:includes("uw-caption-source") then
    local inlines = {pandoc.RawInline("latex", "{\\itshape ")}
    append_all(inlines, span.content)
    table.insert(inlines, pandoc.RawInline("latex", "}"))
    return inlines
  end
end

-- Preserve semantic credit spans until short captions have been computed.
-- Citeproc runs before this filter, including citations inside the spans.
return {{Figure = figure_caption, Table = table_caption}, {Span = source_style}}
