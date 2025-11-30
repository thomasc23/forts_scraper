# Animated Map of US Forts Over Time
# Creates an animated ggplot showing fort locations appearing by year

# Install packages if needed
packages <- c("ggplot2", "gganimate", "sf", "DBI", "RSQLite", "dplyr", "tigris", "gifski")
install_if_missing <- function(pkg) {
  if (!requireNamespace(pkg, quietly = TRUE)) {
    install.packages(pkg)
  }
}
lapply(packages, install_if_missing)

# Load libraries
library(ggplot2)
library(gganimate)
library(sf)
library(DBI)
library(RSQLite)
library(dplyr)
library(tigris)

# Set tigris options for caching
options(tigris_use_cache = TRUE)

# Connect to the SQLite database
con <- dbConnect(RSQLite::SQLite(), "data/forts.db")

# Query fort data with coordinates and dates
forts <- dbGetQuery(con, "
  SELECT
    fort_id,
    name_primary,
    state_territory,
    state_full_name,
    lat,
    lon,
    earliest_year,
    latest_year,
    geocode_confidence,
    nationality
  FROM forts
  WHERE lat IS NOT NULL
    AND lon IS NOT NULL
    AND earliest_year IS NOT NULL
    AND geocode_confidence != 'failed'
")

dbDisconnect(con)

cat("Loaded", nrow(forts), "forts with coordinates and dates\n")

# Filter to continental US (exclude Alaska, Hawaii, territories)
continental_states <- c(
  "Alabama", "Arizona", "Arkansas", "California", "Colorado", "Connecticut",
  "Delaware", "Florida", "Georgia", "Idaho", "Illinois", "Indiana", "Iowa",
  "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland", "Massachusetts",
  "Michigan", "Minnesota", "Mississippi", "Missouri", "Montana", "Nebraska",
  "Nevada", "New Hampshire", "New Jersey", "New Mexico", "New York",
  "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon", "Pennsylvania",
  "Rhode Island", "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah",
  "Vermont", "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming"
)

forts_continental <- forts %>%
  filter(state_full_name %in% continental_states) %>%
  filter(lon > -130 & lon < -65) %>%
  filter(lat > 24 & lat < 50)

cat("Filtered to", nrow(forts_continental), "continental US forts\n")

# Get US county boundaries (2020 census)
cat("Downloading county boundaries...\n")
counties <- counties(cb = TRUE, resolution = "20m", year = 2020)

# Filter to continental US
counties_continental <- counties %>%
  filter(!STATEFP %in% c("02", "15", "60", "66", "69", "72", "78"))

# Create year bins - focus on 1600-1900 range where most forts were built
# and use larger bins for cleaner animation
forts_continental <- forts_continental %>%
  filter(earliest_year >= 1600 & earliest_year <= 1950)

cat("Filtered to", nrow(forts_continental), "forts in 1600-1950 range\n")

# Create decade bins for animation
forts_continental <- forts_continental %>%
  mutate(decade = floor(earliest_year / 25) * 25)  # 25-year bins

year_breaks <- sort(unique(forts_continental$decade))
cat("Animation will have", length(year_breaks), "frames (25-year periods)\n")

# Build cumulative dataset for animation
forts_cumulative <- do.call(rbind, lapply(year_breaks, function(yr) {
  forts_continental %>%
    filter(earliest_year <= yr) %>%
    mutate(frame_year = yr)
}))

cat("Created cumulative dataset with", nrow(forts_cumulative), "rows\n")

# Create the animated plot using geom_point (not geom_sf for points)
cat("Creating animation...\n")

p <- ggplot() +
  # County boundaries (static)
  geom_sf(data = counties_continental, fill = "gray95", color = "gray70", linewidth = 0.1) +

  # Fort locations as points (not sf)
  geom_point(
    data = forts_cumulative,
    aes(x = lon, y = lat, color = geocode_confidence),
    size = 1.5,
    alpha = 0.7
  ) +

  # Coordinate system matching the sf data
 coord_sf(xlim = c(-125, -67), ylim = c(25, 50), crs = 4326) +

  # Color scale for confidence levels
  scale_color_manual(
    values = c(
      "exact" = "#2ecc71",
      "locality" = "#3498db",
      "approximate" = "#9b59b6",
      "county" = "#e67e22",
      "state" = "#e74c3c"
    ),
    name = "Location\nConfidence"
  ) +

  # Theme
  theme_minimal() +
  theme(
    plot.title = element_text(size = 18, face = "bold", hjust = 0.5),
    plot.subtitle = element_text(size = 14, hjust = 0.5, color = "gray40"),
    legend.position = "right",
    panel.grid = element_blank(),
    axis.text = element_blank(),
    axis.title = element_blank(),
    plot.background = element_rect(fill = "white", color = NA),
    panel.background = element_rect(fill = "white", color = NA)
  ) +

  # Labels with animation frame info
  labs(
    title = "North American Forts Through {closest_state}",
    subtitle = "Cumulative forts established",
    caption = "Data: northamericanforts.com"
  ) +

  # Animation settings - wrap = FALSE prevents looping back to frame 1
  transition_states(frame_year, transition_length = 1, state_length = 2, wrap = FALSE) +
  ease_aes('linear')

# Render animation
anim <- animate(
  p,
  nframes = length(year_breaks) * 2,
  fps = 4,
  width = 1000,
  height = 700,
  renderer = gifski_renderer()
)

# Save animation
anim_save("fort_animation.gif", animation = anim)
cat("\nAnimation saved to: fort_animation.gif\n")

# Also create a static map showing all forts
cat("Creating static map...\n")

p_static <- ggplot() +
  geom_sf(data = counties_continental, fill = "gray95", color = "gray70", linewidth = 0.1) +
  geom_point(
    data = forts_continental,
    aes(x = lon, y = lat, color = geocode_confidence),
    size = 1.2,
    alpha = 0.6
  ) +
  coord_sf(xlim = c(-125, -67), ylim = c(25, 50), crs = 4326) +
  scale_color_manual(
    values = c(
      "exact" = "#2ecc71",
      "locality" = "#3498db",
      "approximate" = "#9b59b6",
      "county" = "#e67e22",
      "state" = "#e74c3c"
    ),
    name = "Location\nConfidence"
  ) +
  theme_minimal() +
  theme(
    plot.title = element_text(size = 16, face = "bold", hjust = 0.5),
    plot.subtitle = element_text(size = 12, hjust = 0.5, color = "gray40"),
    legend.position = "right",
    panel.grid = element_blank(),
    axis.text = element_blank(),
    axis.title = element_blank(),
    plot.background = element_rect(fill = "white", color = NA)
  ) +
  labs(
    title = "All North American Forts (1600-1950)",
    subtitle = paste(nrow(forts_continental), "forts with geocoded locations"),
    caption = "Data: northamericanforts.com"
  )

ggsave("fort_map_static.png", p_static, width = 12, height = 8, dpi = 150)
cat("Static map saved to: fort_map_static.png\n")

cat("\nDone!\n")
