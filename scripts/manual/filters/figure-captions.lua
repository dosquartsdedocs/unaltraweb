local function append_all(destination, values)
  for _, value in ipairs(values) do
    table.insert(destination, value)
  end
end

function Figure(figure)
  if not FORMAT:match("latex") or #figure.caption.long == 0 then
    return nil
  end

  local caption = {pandoc.RawInline("latex", "\\caption{")}
  for index, block in ipairs(figure.caption.long) do
    if index > 1 then
      table.insert(caption, pandoc.Space())
    end
    if block.content then
      append_all(caption, block.content)
    else
      table.insert(caption, pandoc.Str(pandoc.utils.stringify(block)))
    end
  end
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
