#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use lopdf::{Document, Object};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use tauri::Manager;
use base64::{Engine as _, engine::general_purpose};

#[derive(Debug, Serialize, Deserialize)]
struct PdfPage {
    page_number: usize,
    width: f64,
    height: f64,
    rotation: i32,
    thumbnail: String,
}

#[derive(Debug, Serialize, Deserialize)]
struct PdfInfo {
    path: String,
    page_count: usize,
    pages: Vec<PdfPage>,
}

#[tauri::command]
async fn load_pdf(path: String) -> Result<PdfInfo, String> {
    let doc = Document::load(&path).map_err(|e| e.to_string())?;
    let page_count = doc.get_pages().len();
    let mut pages = Vec::new();

    for (i, _page_id) in doc.get_pages().iter().enumerate() {
        let page_number = i + 1;
        
        // Get page dimensions
        let (width, height) = get_page_dimensions(&doc, page_number)?;
        
        // Generate thumbnail (simplified - just placeholder for now)
        let thumbnail = generate_thumbnail_placeholder(page_number);
        
        pages.push(PdfPage {
            page_number,
            width,
            height,
            rotation: 0,
            thumbnail,
        });
    }

    Ok(PdfInfo {
        path,
        page_count,
        pages,
    })
}

fn get_page_dimensions(doc: &Document, page_num: usize) -> Result<(f64, f64), String> {
    let pages = doc.get_pages();
    let page_id = pages.get(&(page_num as u32)).ok_or("Page not found")?;
    let page = doc.get_object(*page_id).map_err(|e| e.to_string())?;
    
    if let Object::Dictionary(dict) = page {
        if let Ok(Object::Array(media_box)) = dict.get(b"MediaBox") {
            if media_box.len() >= 4 {
                let width = media_box[2].as_i64().unwrap_or(595) as f64 - media_box[0].as_i64().unwrap_or(0) as f64;
                let height = media_box[3].as_i64().unwrap_or(842) as f64 - media_box[1].as_i64().unwrap_or(0) as f64;
                return Ok((width, height));
            }
        }
    }
    
    Ok((595.0, 842.0)) // Default A4 size
}

fn generate_thumbnail_placeholder(page_num: usize) -> String {
    // Simple placeholder - in production, you'd generate actual thumbnails
    let svg_content = format!(
        "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"100\" height=\"141\" viewBox=\"0 0 100 141\">\
         <rect width=\"100\" height=\"141\" fill=\"#f0f0f0\" stroke=\"#cccccc\"/>\
         <text x=\"50\" y=\"70\" text-anchor=\"middle\" font-family=\"Arial\" font-size=\"24\" fill=\"#666666\">{}</text>\
         </svg>",
        page_num
    );
    format!("data:image/svg+xml;base64,{}", general_purpose::STANDARD.encode(svg_content))
}

#[tauri::command]
async fn save_pdf(
    path: String,
    output_path: String,
    page_order: Vec<usize>,
    rotations: BTreeMap<usize, i32>,
    deleted_pages: Vec<usize>,
) -> Result<(), String> {
    let doc = Document::load(&path).map_err(|e| e.to_string())?;
    let mut new_doc = Document::with_version("1.5");
    
    // Copy metadata
    if let Ok(info) = doc.trailer.get(b"Info") {
        new_doc.trailer.set("Info", info.clone());
    }
    
    // Process pages in the specified order
    for &page_num in &page_order {
        if deleted_pages.contains(&page_num) {
            continue;
        }
        
        let pages = doc.get_pages();
        if let Some(&page_id) = pages.get(&(page_num as u32)) {
            // Clone the page
            let page = doc.get_object(page_id).map_err(|e| e.to_string())?;
            let mut page_dict = if let Object::Dictionary(dict) = page {
                dict.clone()
            } else {
                continue;
            };
            
            // Apply rotation if needed
            if let Some(&rotation) = rotations.get(&page_num) {
                if rotation != 0 {
                    page_dict.set("Rotate", Object::Integer(rotation as i64));
                }
            }
            
            // Add page to new document
            let new_page_id = new_doc.new_object_id();
            new_doc.objects.insert(new_page_id, Object::Dictionary(page_dict));
            
            // Update page tree - simplified for now
            // In production, you'd properly build the page tree structure
        }
    }
    
    // Save the new document
    new_doc.save(output_path).map_err(|e| e.to_string())?;
    
    Ok(())
}

#[tauri::command]
async fn merge_pdfs(paths: Vec<String>, output_path: String) -> Result<(), String> {
    if paths.is_empty() {
        return Err("No PDFs to merge".to_string());
    }
    
    let mut merged_doc = Document::load(&paths[0]).map_err(|e| e.to_string())?;
    
    for path in paths.iter().skip(1) {
        let doc = Document::load(path).map_err(|e| e.to_string())?;
        
        // Merge pages from doc into merged_doc
        // This is a simplified version - proper implementation would handle resources, etc.
        for (_, page_id) in doc.get_pages() {
            if let Ok(page) = doc.get_object(page_id) {
                let new_page_id = merged_doc.new_object_id();
                merged_doc.objects.insert(new_page_id, page.clone());
            }
        }
    }
    
    merged_doc.save(output_path).map_err(|e| e.to_string())?;
    
    Ok(())
}



fn main() {
    tauri::Builder::default()
        .setup(|app| {
            #[cfg(debug_assertions)]
            {
                let window = app.get_webview_window("main").unwrap();
                window.open_devtools();
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            load_pdf,
            save_pdf,
            merge_pdfs
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}