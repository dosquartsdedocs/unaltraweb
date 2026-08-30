# frozen_string_literal: true

require_relative "unaltraweb/version"

%w[
  bibliography_profiles
  localized_visual_sources
  callouts
  code_blocks
  computation_figure_images
  vega_visual_images
  computation_sources
  details
  external-posts
  file-exists
  figure_captions
  google-scholar-citations
  hide-custom-bibtex
  inspirehep-citations
  mermaid_mmd_images
  content_search_index
  profile-pages
  remove-accents
  search-data
  theme-cache-bust
  web_capture_images
].each do |plugin|
  require File.expand_path("../_plugins/#{plugin}", __dir__)
end
