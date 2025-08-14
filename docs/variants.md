# Aircraft « Variants »

A given aircraft might have different _«variants»_.

For example, Airbus A321 neo, ICAO code A21N, can have the following «variants»:

  - A321-251N
  - A321-252N
  - A321-253N
  - A321-271N
  - A321-272N
  - A321-251NX
  - A321-252NX
  - A321-253NX
  - A321-271NX
  - A321-272NX
  - A321-253NY
  - A321-271NY

They are all recognized as ICAO code A21N.

Variants differt in engine make and models, aircraft length and capacity (LR, XLR),
and additional fuel tanks.

While this often has little effect on managed devices,
it might be important to know which variant a pilot is currently using.

Since X-Plane does not provide a mechanism to enter and manage variants,
Winwing application created one.

Mechanism is simple and based on regular X-Plane features.

Ultimately, the variant of an aircraft model is a character string
(for example 272NX, or 271NY).

To deternmine the variant, it is necessary to read one or more X-Plane datarefs.
Then, from the values of the datarefs, an aircraft model/type will use
a custom function to produce the appropriate variant string.

For example, an aircraft might list the engine manufacturer, and the engine
maximum trust.
It may also list the number of auxialiary (center) tanks.

From the values of these parameters, it is possible to determine the variant
of the aircraft currently used.

If defined, present, and not empty, the variant string will be used
to see if a custom aircraft configuration exists for this variant.

If none is found, the aircraft will use the version without variant.
