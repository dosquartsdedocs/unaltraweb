-- Consume the core caption filter's output, preserving its short captions/credits.
local continuation = "continued"
local function metadata(meta)
  continuation = pandoc.utils.stringify(meta["continuation-label"] or "continued")
end

local function figures(blocks)
  local result, figure = pandoc.List(), nil
  for _, block in ipairs(blocks) do
    if block.t == "RawBlock" and block.text == "\\begin{figure}[H]\n\\centering" then
      assert(not figure, "Nested practice figure")
      figure = pandoc.List()
    elseif figure and block.t == "RawBlock" and block.text == "\\end{figure}" then
      assert(#figure == 2, "Practice figures require one caption and one image")
      local caption = pandoc.write(pandoc.Pandoc({figure[1]}), "latex"):gsub("%s+$", "")
      local image = pandoc.write(pandoc.Pandoc({figure[2]}), "latex"):gsub("%s+$", "")
      result:insert(pandoc.RawBlock("latex", "\\PracticeFigure{" .. caption .. "}{" .. image .. "}"))
      figure = nil
    elseif figure then figure:insert(block)
    else result:insert(block) end
  end
  assert(not figure, "Unclosed practice figure")
  return result
end

local function table_caption(element)
  assert(#element.caption.long > 0, "Practice tables require a Table: caption")
  local rendered = pandoc.write(pandoc.Pandoc({element}), "latex")
  local caption = pandoc.write(pandoc.Pandoc(element.caption.long), "latex"):gsub("%s+$", "")
  rendered = rendered:gsub("\\endfirsthead", function()
    return "\\endfirsthead\n\\caption[]{" .. caption .. " (" .. continuation .. ")}\\tabularnewline"
  end, 1)
  return pandoc.RawBlock("latex", rendered)
end

return {{Meta = metadata}, {Blocks = figures, Table = table_caption}}
