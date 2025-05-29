from PIL import Image, ImageDraw, ImageFont
import os

def create_no_preview_image():
    # Create a new image with a dark gray background
    width = 512
    height = 512
    img = Image.new('RGB', (width, height), color='#2C2C2C')
    draw = ImageDraw.Draw(img)
    
    # Add text
    text = "No Preview\nAvailable"
    text_color = "#FFFFFF"
    
    # Calculate text size and position
    try:
        font = ImageFont.truetype("arial.ttf", 60)
    except:
        font = ImageFont.load_default()
    
    # Center the text
    text_bbox = draw.multiline_textbbox((0, 0), text, font=font, align="center")
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    x = (width - text_width) / 2
    y = (height - text_height) / 2
    
    # Draw the text
    draw.multiline_text((x, y), text, fill=text_color, font=font, align="center")
    
    # Save the image
    output_path = os.path.join(os.path.dirname(__file__), "no_preview.png")
    img.save(output_path, "PNG", optimize=True)
    print(f"Created fallback image at: {output_path}")

if __name__ == "__main__":
    create_no_preview_image() 