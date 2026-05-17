# frozen_string_literal: true

require_relative "unaltraweb/version"

%w[
  details
  external-posts
  file-exists
  figure_captions
  google-scholar-citations
  hide-custom-bibtex
  inspirehep-citations
  mermaid_mmd_images
  manual_search_index
  profile-pages
  remove-accents
  search-data
  theme-cache-bust
].each do |plugin|
  require File.expand_path("../_plugins/#{plugin}", __dir__)
end
