// get the ninja-keys element
const ninja = document.querySelector('ninja-keys');

// add the home and posts menu items
ninja.data = [{
      id: "nav-home",
      title: "Home",
      section: "Navigation",
      handler: () => {
        window.location.href = "/unaltraweb/en/";
      },
    },{id: "dropdown-the-project",
              title: "The project",
              description: "",
              section: "Dropdown",
              handler: () => {
                window.location.href = "/unaltraweb/en/the-project/";
              },
            },{id: "dropdown-former-projects",
              title: "Former projects",
              description: "",
              section: "Dropdown",
              handler: () => {
                window.location.href = "/unaltraweb/en/former-projects/";
              },
            },{id: "dropdown-el-projecte",
              title: "El projecte",
              description: "",
              section: "Dropdown",
              handler: () => {
                window.location.href = "/unaltraweb/ca/el-projecte/";
              },
            },{id: "dropdown-projectes-anteriors",
              title: "Projectes anteriors",
              description: "",
              section: "Dropdown",
              handler: () => {
                window.location.href = "/unaltraweb/ca/projectes-anteriors/";
              },
            },{id: "dropdown-el-proyecto",
              title: "El proyecto",
              description: "",
              section: "Dropdown",
              handler: () => {
                window.location.href = "/unaltraweb/es/el-proyecto/";
              },
            },{id: "dropdown-proyectos-previos",
              title: "Proyectos previos",
              description: "",
              section: "Dropdown",
              handler: () => {
                window.location.href = "/unaltraweb/es/proyectos-previos/";
              },
            },{id: "nav-outputs",
          title: "Outputs",
          description: "Datasets, software tools, maps, indicator fiches, calculations, and other project products.",
          section: "Navigation",
          handler: () => {
            window.location.href = "/unaltraweb/en/outputs/";
          },
        },{id: "nav-productes",
          title: "Productes",
          description: "Dades, eines, mapes, fitxes d&#39;indicadors, calculs i altres productes del projecte.",
          section: "Navigation",
          handler: () => {
            window.location.href = "/unaltraweb/ca/productes/";
          },
        },{id: "nav-productos",
          title: "Productos",
          description: "Datos, herramientas, mapas, fichas de indicadores, calculos y otros productos del proyecto.",
          section: "Navigation",
          handler: () => {
            window.location.href = "/unaltraweb/es/productos/";
          },
        },{id: "nav-equip",
          title: "Equip",
          description: "",
          section: "Navigation",
          handler: () => {
            window.location.href = "/unaltraweb/ca/equip/";
          },
        },{id: "nav-equipo",
          title: "Equipo",
          description: "",
          section: "Navigation",
          handler: () => {
            window.location.href = "/unaltraweb/es/equipo/";
          },
        },{id: "nav-team",
          title: "Team",
          description: "",
          section: "Navigation",
          handler: () => {
            window.location.href = "/unaltraweb/en/team/";
          },
        },{id: "nav-publicaciones",
          title: "Publicaciones",
          description: "Resultados cientificos e informes tecnicos.",
          section: "Navigation",
          handler: () => {
            window.location.href = "/unaltraweb/es/publicaciones/";
          },
        },{id: "nav-publicacions",
          title: "Publicacions",
          description: "Resultats cientifics i informes tecnics.",
          section: "Navigation",
          handler: () => {
            window.location.href = "/unaltraweb/ca/publicacions/";
          },
        },{id: "nav-publications",
          title: "Publications",
          description: "Scientific outputs and technical reports.",
          section: "Navigation",
          handler: () => {
            window.location.href = "/unaltraweb/en/publications/";
          },
        },{id: "nav-repositories",
          title: "Repositories",
          description: "Source code and reproducible workflows.",
          section: "Navigation",
          handler: () => {
            window.location.href = "/unaltraweb/en/repositories/";
          },
        },{id: "nav-repositorios",
          title: "Repositorios",
          description: "Codigo fuente y flujos reproducibles.",
          section: "Navigation",
          handler: () => {
            window.location.href = "/unaltraweb/es/repositorios/";
          },
        },{id: "nav-repositoris",
          title: "Repositoris",
          description: "Codi font i fluxos reproduibles.",
          section: "Navigation",
          handler: () => {
            window.location.href = "/unaltraweb/ca/repositoris/";
          },
        },{id: "nav-theses",
          title: "Theses",
          description: "Ongoing or already finished PhD theses.",
          section: "Navigation",
          handler: () => {
            window.location.href = "/unaltraweb/theses/";
          },
        },{id: "nav-blog",
          title: "Blog",
          description: "Notes, methods, and development updates.",
          section: "Navigation",
          handler: () => {
            window.location.href = "/unaltraweb/en/blog/";
          },
        },{id: "nav-blog",
          title: "Blog",
          description: "Notes, metodes i actualitzacions de desenvolupament.",
          section: "Navigation",
          handler: () => {
            window.location.href = "/unaltraweb/ca/blog/";
          },
        },{id: "nav-blog",
          title: "Blog",
          description: "Notas, metodos y actualizaciones de desarrollo.",
          section: "Navigation",
          handler: () => {
            window.location.href = "/unaltraweb/es/blog/";
          },
        },{id: "nav-bookshelf",
          title: "Bookshelf",
          description: "",
          section: "Navigation",
          handler: () => {
            window.location.href = "/unaltraweb/books/";
          },
        },{id: "nav-cv",
          title: "CV",
          description: "This is a description of the page. You can modify it in &#39;_pages/cv.md&#39;. You can also change or remove the top pdf download button.",
          section: "Navigation",
          handler: () => {
            window.location.href = "/unaltraweb/cv/";
          },
        },{id: "post-a-post-with-plotly-js",
        
          title: "a post with plotly.js",
        
        description: "this is what included plotly.js code could look like",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2025/plotly/";
          
        },
      },{id: "post-a-post-with-image-galleries",
        
          title: "a post with image galleries",
        
        description: "this is what included image galleries could look like",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2024/photo-gallery/";
          
        },
      },{id: "post-google-gemini-updates-flash-1-5-gemma-2-and-project-astra",
        
          title: 'Google Gemini updates: Flash 1.5, Gemma 2 and Project Astra <svg width="1.2rem" height="1.2rem" top=".5rem" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><path d="M17 13.5v6H5v-12h6m3-3h6v6m0-6-9 9" class="icon_svg-stroke" stroke="#999" stroke-width="1.5" fill="none" fill-rule="evenodd" stroke-linecap="round" stroke-linejoin="round"></path></svg>',
        
        description: "We’re sharing updates across our Gemini family of models and a glimpse of Project Astra, our vision for the future of AI assistants.",
        section: "Posts",
        handler: () => {
          
            window.open("https://blog.google/technology/ai/google-gemini-update-flash-ai-assistant-io-2024/", "_blank");
          
        },
      },{id: "post-a-post-with-tabs",
        
          title: "a post with tabs",
        
        description: "this is what included tabs in a post could look like",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2024/tabs/";
          
        },
      },{id: "post-a-post-with-typograms",
        
          title: "a post with typograms",
        
        description: "this is what included typograms code could look like",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2024/typograms/";
          
        },
      },{id: "post-a-post-that-can-be-cited",
        
          title: "a post that can be cited",
        
        description: "this is what a post that can be cited looks like",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2024/post-citation/";
          
        },
      },{id: "post-a-post-with-pseudo-code",
        
          title: "a post with pseudo code",
        
        description: "this is what included pseudo code could look like",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2024/pseudocode/";
          
        },
      },{id: "post-a-post-with-code-diff",
        
          title: "a post with code diff",
        
        description: "this is how you can display code diffs",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2024/code-diff/";
          
        },
      },{id: "post-a-post-with-advanced-image-components",
        
          title: "a post with advanced image components",
        
        description: "this is what advanced image components could look like",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2024/advanced-images/";
          
        },
      },{id: "post-a-post-with-vega-lite",
        
          title: "a post with vega lite",
        
        description: "this is what included vega lite code could look like",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2024/vega-lite/";
          
        },
      },{id: "post-a-post-with-geojson",
        
          title: "a post with geojson",
        
        description: "this is what included geojson code could look like",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2024/geojson-map/";
          
        },
      },{id: "post-a-post-with-echarts",
        
          title: "a post with echarts",
        
        description: "this is what included echarts code could look like",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2024/echarts/";
          
        },
      },{id: "post-a-post-with-chart-js",
        
          title: "a post with chart.js",
        
        description: "this is what included chart.js code could look like",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2024/chartjs/";
          
        },
      },{id: "post-a-post-with-tikzjax",
        
          title: "a post with TikZJax",
        
        description: "this is what included TikZ code could look like",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2023/tikzjax/";
          
        },
      },{id: "post-a-post-with-bibliography",
        
          title: "a post with bibliography",
        
        description: "an example of a blog post with bibliography",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2023/post-bibliography/";
          
        },
      },{id: "post-a-post-with-jupyter-notebook",
        
          title: "a post with jupyter notebook",
        
        description: "an example of a blog post with jupyter notebook",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2023/jupyter-notebook/";
          
        },
      },{id: "post-a-post-with-custom-blockquotes",
        
          title: "a post with custom blockquotes",
        
        description: "an example of a blog post with custom blockquotes",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2023/custom-blockquotes/";
          
        },
      },{id: "post-a-post-with-table-of-contents-on-a-sidebar",
        
          title: "a post with table of contents on a sidebar",
        
        description: "an example of a blog post with table of contents on a sidebar",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2023/sidebar-table-of-contents/";
          
        },
      },{id: "post-a-post-with-audios",
        
          title: "a post with audios",
        
        description: "this is what included audios could look like",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2023/audios/";
          
        },
      },{id: "post-a-post-with-videos",
        
          title: "a post with videos",
        
        description: "this is what included videos could look like",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2023/videos/";
          
        },
      },{id: "post-displaying-beautiful-tables-with-bootstrap-tables",
        
          title: "displaying beautiful tables with Bootstrap Tables",
        
        description: "an example of how to use Bootstrap Tables",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2023/tables/";
          
        },
      },{id: "post-a-post-with-table-of-contents",
        
          title: "a post with table of contents",
        
        description: "an example of a blog post with table of contents",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2023/table-of-contents/";
          
        },
      },{id: "post-a-post-with-giscus-comments",
        
          title: "a post with giscus comments",
        
        description: "an example of a blog post with giscus comments",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2022/giscus-comments/";
          
        },
      },{id: "post-displaying-external-posts-on-your-al-folio-blog",
        
          title: 'Displaying External Posts on Your al-folio Blog <svg width="1.2rem" height="1.2rem" top=".5rem" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"><path d="M17 13.5v6H5v-12h6m3-3h6v6m0-6-9 9" class="icon_svg-stroke" stroke="#999" stroke-width="1.5" fill="none" fill-rule="evenodd" stroke-linecap="round" stroke-linejoin="round"></path></svg>',
        
        description: "",
        section: "Posts",
        handler: () => {
          
            window.open("https://medium.com/@al-folio/displaying-external-posts-on-your-al-folio-blog-b60a1d241a0a?source=rss-17feae71c3c4------2", "_blank");
          
        },
      },{id: "post-a-post-with-redirect",
        
          title: "a post with redirect",
        
        description: "you can also redirect to assets like pdf",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/assets/pdf/example_pdf.pdf";
          
        },
      },{id: "post-a-post-with-diagrams",
        
          title: "a post with diagrams",
        
        description: "an example of a blog post with diagrams",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2021/diagrams/";
          
        },
      },{id: "post-a-distill-style-blog-post",
        
          title: "a distill-style blog post",
        
        description: "an example of a distill-style blog post and main elements",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2021/distill/";
          
        },
      },{id: "post-a-post-with-twitter",
        
          title: "a post with twitter",
        
        description: "an example of a blog post with twitter",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2020/twitter/";
          
        },
      },{id: "post-a-post-with-disqus-comments",
        
          title: "a post with disqus comments",
        
        description: "an example of a blog post with disqus comments",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2015/disqus-comments/";
          
        },
      },{id: "post-a-post-with-math",
        
          title: "a post with math",
        
        description: "an example of a blog post with some math",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2015/math/";
          
        },
      },{id: "post-a-post-with-code",
        
          title: "a post with code",
        
        description: "an example of a blog post with some code",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2015/code/";
          
        },
      },{id: "post-a-post-with-images",
        
          title: "a post with images",
        
        description: "this is what included images could look like",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2015/images/";
          
        },
      },{id: "post-a-post-with-formatting-and-links",
        
          title: "a post with formatting and links",
        
        description: "march &amp; april, looking forward to summer",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2015/formatting-and-links/";
          
        },
      },{id: "books-the-godfather",
          title: 'The Godfather',
          description: "",
          section: "Books",handler: () => {
              window.location.href = "/unaltraweb/books/the_godfather/";
            },},{id: "news-a-simple-inline-announcement",
          title: 'A simple inline announcement.',
          description: "",
          section: "News",},{id: "news-a-long-announcement-with-details",
          title: 'A long announcement with details',
          description: "",
          section: "News",handler: () => {
              window.location.href = "/unaltraweb/news/announcement_2/";
            },},{id: "news-a-simple-inline-announcement-with-markdown-emoji-sparkles-smile",
          title: 'A simple inline announcement with Markdown emoji! :sparkles: :smile:',
          description: "",
          section: "News",},{id: "outputs-open-geospatial-dataset",
          title: 'Open geospatial dataset',
          description: "Harmonized project dataset ready for reuse and citation.",
          section: "Outputs",handler: () => {
              window.location.href = "/unaltraweb/outputs/1_open-dataset/";
            },},{id: "outputs-interactive-web-map",
          title: 'Interactive web map',
          description: "Browser-based map viewer for exploring project indicators.",
          section: "Outputs",handler: () => {
              window.location.href = "/unaltraweb/outputs/2_interactive-web-map/";
            },},{id: "outputs-methodological-guide",
          title: 'Methodological guide',
          description: "Reproducible workflow for data processing and analysis.",
          section: "Outputs",handler: () => {
              window.location.href = "/unaltraweb/outputs/3_methodological-guide/";
            },},{id: "outputs-policy-brief",
          title: 'Policy brief',
          description: "Action-oriented summary for decision makers and stakeholders.",
          section: "Outputs",handler: () => {
              window.location.href = "/unaltraweb/outputs/4_policy-brief/";
            },},{id: "outputs-territorial-resilience-indicator-social-dimension-communities",
          title: 'Territorial resilience indicator (social dimension: communities)',
          description: "Demo indicator card with methodological sheet, sample calculations, and interpretation thresholds.",
          section: "Outputs",handler: () => {
              window.location.href = "/unaltraweb/outputs/5_territorial-resilience-social-indicator/";
            },},{id: "projects-project-1",
          title: 'project 1',
          description: "with background image",
          section: "Projects",handler: () => {
              window.location.href = "/unaltraweb/projects/1_project/";
            },},{id: "projects-project-2",
          title: 'project 2',
          description: "a project with a background image and giscus comments",
          section: "Projects",handler: () => {
              window.location.href = "/unaltraweb/projects/2_project/";
            },},{id: "projects-project-3-with-very-long-name",
          title: 'project 3 with very long name',
          description: "a project that redirects to another website",
          section: "Projects",handler: () => {
              window.location.href = "/unaltraweb/projects/3_project/";
            },},{id: "projects-project-4",
          title: 'project 4',
          description: "another without an image",
          section: "Projects",handler: () => {
              window.location.href = "/unaltraweb/projects/4_project/";
            },},{id: "projects-project-5",
          title: 'project 5',
          description: "a project with a background image",
          section: "Projects",handler: () => {
              window.location.href = "/unaltraweb/projects/5_project/";
            },},{id: "projects-project-6",
          title: 'project 6',
          description: "a project with no image",
          section: "Projects",handler: () => {
              window.location.href = "/unaltraweb/projects/6_project/";
            },},{id: "projects-project-7",
          title: 'project 7',
          description: "with background image",
          section: "Projects",handler: () => {
              window.location.href = "/unaltraweb/projects/7_project/";
            },},{id: "projects-project-8",
          title: 'project 8',
          description: "an other project with a background image and giscus comments",
          section: "Projects",handler: () => {
              window.location.href = "/unaltraweb/projects/8_project/";
            },},{id: "projects-project-9",
          title: 'project 9',
          description: "another project with an image 🎉",
          section: "Projects",handler: () => {
              window.location.href = "/unaltraweb/projects/9_project/";
            },},{id: "theses-example-thesis",
          title: 'Example thesis',
          description: "",
          section: "Theses",handler: () => {
              window.location.href = "/unaltraweb/theses/001-example/";
            },},{id: "theses-example-thesis",
          title: 'Example thesis',
          description: "",
          section: "Theses",handler: () => {
              window.location.href = "/unaltraweb/theses/002-example/";
            },},{
        id: 'social-email',
        title: 'email',
        section: 'Socials',
        handler: () => {
          window.open("mailto:%79%6F%75@%65%78%61%6D%70%6C%65.%63%6F%6D", "_blank");
        },
      },{
        id: 'social-rss',
        title: 'RSS Feed',
        section: 'Socials',
        handler: () => {
          window.open("/unaltraweb/feed.xml", "_blank");
        },
      },{
        id: 'social-custom_social',
        title: 'Custom_social',
        section: 'Socials',
        handler: () => {
          window.open("https://www.alberteinstein.com/", "_blank");
        },
      },{
      id: 'light-theme',
      title: 'Change theme to light',
      description: 'Change the theme of the site to Light',
      section: 'Theme',
      handler: () => {
        setThemeSetting("light");
      },
    },
    {
      id: 'dark-theme',
      title: 'Change theme to dark',
      description: 'Change the theme of the site to Dark',
      section: 'Theme',
      handler: () => {
        setThemeSetting("dark");
      },
    },
    {
      id: 'system-theme',
      title: 'Use system default theme',
      description: 'Change the theme of the site to System Default',
      section: 'Theme',
      handler: () => {
        setThemeSetting("system");
      },
    },];
