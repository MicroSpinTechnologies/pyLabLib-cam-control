import numpy as np
import matplotlib.pyplot as plt
import tifffile

data = np.load("snap_raw_data.npy")
print(data.shape)
# data shape (1, 1, 1200, 1920)

# Extract the 2D image
image = data[0][0]
print(f"Image data range: {np.min(image)} to {np.max(image)} (dtype: {image.dtype})")

# PROBLEM: The original data uses only 0.67% of the uint16 range (50-490 out of 0-65535)
# This makes TIFF files appear black in viewers that expect full range scaling

# SOLUTION 1: Save original data (appears black in most TIFF viewers)
tifffile.imwrite("test_original.tiff", image, photometric="minisblack")
print("Saved original data (may appear black in TIFF viewers)")

scaled_16bit = ((image - np.min(image)) / (np.max(image) - np.min(image)) * 65535).astype(np.uint16)
tifffile.imwrite("test_16bit_scaled.tiff", scaled_16bit, photometric="minisblack", metadata={"axes": "YX"})
print(f"Saved 16-bit scaled: {np.min(scaled_16bit)} to {np.max(scaled_16bit)}")

# Create a stack with duplicated frames
num_frames = 5  # Number of duplicate frames to create
stack_original = np.stack([image] * num_frames)  # Shape: (5, 1200, 1920)
stack_scaled = np.stack([scaled_16bit] * num_frames)  # Shape: (5, 1200, 1920)

# Save stacks as multi-frame TIFF files
tifffile.imwrite("test_stack_original.tiff", stack_original, photometric="minisblack", metadata={"axes": "ZYX"})
print(f"Saved original stack: {stack_original.shape} frames")

tifffile.imwrite("test_stack_scaled.tiff", stack_scaled, photometric="minisblack", metadata={"axes": "ZYX"})
print(f"Saved scaled stack: {stack_scaled.shape} frames")

# Alternative: Create a stack with slight variations (e.g., adding noise)
stack_with_noise = np.stack([image + np.random.normal(0, 2, image.shape).astype(np.uint16) for _ in range(num_frames)])
tifffile.imwrite("test_stack_noise.tiff", stack_with_noise, photometric="minisblack", metadata={"axes": "ZYX"})
print(f"Saved noise-varied stack: {stack_with_noise.shape} frames")

print("\nWhy matplotlib works but TIFF appears black:")
print("- matplotlib.imshow() auto-scales display range (50→black, 490→white)")
print("- TIFF viewers often expect full data type range (0-65535 for uint16)")
print("- Your data uses only ~0.67% of available range")

# Display comparison
plt.figure(figsize=(15, 5))

plt.subplot(1, 1, 1)
plt.imshow(image, cmap="gray")
plt.title(f"Original\n(auto-scaled: {np.min(image)}-{np.max(image)})")
plt.colorbar()

plt.tight_layout()
plt.show()
