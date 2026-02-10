library(shiny)
library(bslib)
library(dplyr)
library(tidyr)
library(ggplot2)
library(DT)
library(plotly)
library(readr)
library(ggvenn)

# Define UI
ui <- page_sidebar(
  title = "Glycan Comparison",
  sidebar = sidebar(
    fileInput("file", "Upload Glycoprep Output (.tsv)", accept = ".tsv"),
    numericInput("confidence_threshold", "Confidence Threshold", value = 0.9, min = 0, max = 1, step = 0.05),
    selectInput("group_by", "Comparison Group", choices = c("condition", "severity", "sex"), selected = "condition"),
    numericInput("dominance_pct", "Dominance Threshold (%)", value = 75, min = 1, max = 100),
    actionButton("reset", "Reset Filters")
  ),
  navset_card_underline(
    nav_panel("Overview",
              layout_columns(
                card(card_header("Total Glycan Area"), plotlyOutput("total_area_plot")),
                card(card_header("Glycan Dominance"), plotlyOutput("dominance_plot"))
              )
    ),
    nav_panel("Multivariate (PCA)",
              card(
                card_header("Principal Component Analysis"),
                plotlyOutput("pca_plot")
              )
    ),
    nav_panel("Differential Analysis",
              card(
                card_header("Composition Heatmap"),
                plotOutput("heatmap_plot", height = "600px")
              )
    ),
    nav_panel("Overlap",
              card(
                card_header("Glycan Overlap by Group"),
                plotOutput("venn_plot")
              )
    )
  )
)

# Define Server
server <- function(input, output, session) {
  options(shiny.maxRequestSize = 30*1024^2)
  
  # Reactive Data Loader
  data <- reactive({
    req(input$file)
    df <- read_tsv(input$file$datapath, show_col_types = FALSE)
    
    if("confidence" %in% names(df)){
      df <- df %>% filter(confidence >= input$confidence_threshold)
    }
    
    # Ensure patient and group columns exist
    req("patient" %in% names(df))
    req(input$group_by %in% names(df))
    
    return(df)
  })
  
  # --- Data Processing ---
  
  # Relative Abundance per Patient
  rel_abundance <- reactive({
    req(data())
    data() %>%
      group_by(patient) %>%
      mutate(
        total_area_patient = sum(area, na.rm = TRUE),
        rel_abundance_pct = (area / total_area_patient) * 100
      ) %>%
      ungroup()
  })
  
  # Patient Metadata (Unique mapping of patient -> condition/group)
  patient_meta <- reactive({
    req(data())
    data() %>%
      select(patient, !!sym(input$group_by)) %>%
      distinct()
  })
  
  # --- Overview Plots ---
  
  output$total_area_plot <- renderPlotly({
    req(data())
    
    df_area <- data() %>%
      group_by(patient, !!sym(input$group_by)) %>%
      summarise(total_area = sum(area, na.rm = TRUE), .groups = "drop")
    
    p <- ggplot(df_area, aes(x = !!sym(input$group_by), y = total_area, fill = !!sym(input$group_by))) +
      geom_boxplot(alpha = 0.6) +
      geom_jitter(width = 0.2, alpha = 0.5) +
      theme_minimal() +
      labs(y = "Total Glycan Area") +
      theme(legend.position = "none")
    
    ggplotly(p)
  })
  
  output$dominance_plot <- renderPlotly({
    req(rel_abundance())
    
    threshold <- input$dominance_pct
    
    df_dom <- rel_abundance() %>%
      group_by(patient, !!sym(input$group_by)) %>%
      arrange(patient, desc(rel_abundance_pct)) %>%
      mutate(cum_abundance = cumsum(rel_abundance_pct)) %>%
      summarise(
        n_glycans = min(which(cum_abundance >= threshold)),
        .groups = "drop"
      )
    
    p <- ggplot(df_dom, aes(x = !!sym(input$group_by), y = n_glycans, fill = !!sym(input$group_by))) +
      geom_boxplot(alpha = 0.6) +
      geom_jitter(width = 0.2, alpha = 0.5) +
      theme_minimal() +
      labs(y = paste0("N Glycans for ", threshold, "% Abundance")) +
      theme(legend.position = "none")
    
    ggplotly(p)
  })
  
  # --- Multivariate (PCA) ---
  
  output$pca_plot <- renderPlotly({
    req(rel_abundance(), patient_meta())
    
    # Pivot to wide format (Patients x Glycans)
    wide_df <- rel_abundance() %>%
      select(patient, Composition, rel_abundance_pct) %>%
      pivot_wider(names_from = Composition, values_from = rel_abundance_pct, values_fill = 0)
    
    # Matrix for PCA
    mat <- as.matrix(wide_df %>% select(-patient))
    rownames(mat) <- wide_df$patient
    
    # Log transform (log1p)
    mat_log <- log1p(mat)
    
    # PCA
    # Need to handle cases with too few samples or zero variance
    tryCatch({
      # Filter zero variance columns
      mat_log <- mat_log[, apply(mat_log, 2, var) > 0] 
      
      pca_res <- prcomp(mat_log, center = TRUE, scale. = TRUE)
      
      # Prepare plot data
      pca_plot_df <- as.data.frame(pca_res$x) %>%
        mutate(patient = rownames(pca_res$x)) %>%
        left_join(patient_meta(), by = "patient")
      
      var_exp <- round(summary(pca_res)$importance[2, 1:2] * 100, 1)
      
      p <- ggplot(pca_plot_df, aes(x = PC1, y = PC2, color = !!sym(input$group_by), text = patient)) +
        geom_point(size = 3, alpha = 0.8) +
        theme_minimal() +
        labs(
          x = paste0("PC1 (", var_exp[1], "%)"),
          y = paste0("PC2 (", var_exp[2], "%)")
        )
      
      ggplotly(p)
      
    }, error = function(e) {
      # Return empty plot with error message if PCA fails
      plot_ly() %>% 
        layout(title = paste("PCA failed:", e$message))
    })
  })
  
  # --- Differential Analysis (Heatmap) ---
  
  output$heatmap_plot <- renderPlot({
    req(rel_abundance())
    
    # Aggregate by Group and Composition
    # To normalize: N unique patients in this group / Total unique patients in this group
    # BUT the script uses N/M where N is presence count, M is total group count.
    
    # 1. Total patients per group
    group_counts <- patient_meta() %>%
      count(!!sym(input$group_by), name = "total_in_group")
    
    # 2. Patients with this glycan per group
    glycan_counts <- rel_abundance() %>%
      group_by(!!sym(input$group_by), Composition) %>%
      summarise(present_in = n_distinct(patient), .groups = "drop")
    
    # 3. Combine
    plot_data <- glycan_counts %>%
      left_join(group_counts, by = input$group_by) %>%
      mutate(freq = present_in / total_in_group)
    
    ggplot(plot_data, aes(x = !!sym(input$group_by), y = Composition, fill = freq)) +
      geom_tile(color = "white") +
      geom_text(aes(label = paste0(present_in, "/", total_in_group)), size = 3) +
      scale_fill_gradient2(low = "white", mid = "blue", high = "black", midpoint = 0.5) +
      theme_minimal() +
      labs(fill = "Proportion") +
      theme(axis.text.x = element_text(angle = 45, hjust = 1))
  })
  
  # --- Overlap (Venn) ---
  
  output$venn_plot <- renderPlot({
    req(rel_abundance())
    
    # Prepare list for Venn
    # Use split() instead of deframe() to avoid tidyr/tibble dependency issues
    df_venn <- rel_abundance() %>%
      select(!!sym(input$group_by), Composition) %>%
      distinct()
    
    venn_list <- split(df_venn$Composition, df_venn[[input$group_by]])
    
    # Limit to first 4 groups if more exist (ggvenn limit)
    if(length(venn_list) > 4){
      venn_list <- venn_list[1:4]
      showNotification("Showing Venn diagram for first 4 groups only.", type = "warning")
    }
    
    if (requireNamespace("ggvenn", quietly = TRUE)) {
      ggvenn::ggvenn(venn_list, show_percentage = TRUE, stroke_size = 0.5)
    } else {
      plot(c(0, 1), c(0, 1), ann = F, bty = 'n', type = 'n', xaxt = 'n', yaxt = 'n')
      text(x = 0.5, y = 0.5, paste("Package 'ggvenn' is missing.\nPlease install it with: install.packages('ggvenn')"), 
           cex = 1.6, col = "red")
    }
  })
}

shinyApp(ui, server)
